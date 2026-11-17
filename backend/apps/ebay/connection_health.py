"""Owned diagnostic metadata only; reading health never contacts eBay."""
from copy import deepcopy
from dataclasses import dataclass
from datetime import timedelta
import logging
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import DatabaseError, IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from apps.ebay.diagnostics import OPERATIONS, diagnostic, public_diagnostic, safe_exception
from apps.ebay.models import EbayAccountSnapshot, EbayAppToken, EbayConnectionHealth, EbayCredential, MerchantLocation

logger = logging.getLogger(__name__)
CHECK_COOLDOWN = timedelta(minutes=5)


@dataclass(frozen=True)
class Attempt:
    environment: str
    principal: str
    connection_id: uuid.UUID
    sequence: int
    operation: str
    using: str = "default"


def environment():
    from integrations.ebay import effective_environment
    return effective_environment()


def _row(principal, using="default"):
    try:
        with transaction.atomic(using=using):
            return EbayConnectionHealth.objects.using(using).get_or_create(environment=environment(), principal=principal)[0]
    except IntegrityError:
        return EbayConnectionHealth.objects.using(using).get(environment=environment(), principal=principal)


def reset_seller():
    row = _row("seller")
    EbayConnectionHealth.objects.filter(pk=row.pk).update(connection_id=uuid.uuid4(), operations={},
        revision=F("revision") + 1, check_id=None, check_started_at=None, check_completed_at=None,
        next_check_at=None, updated_at=timezone.now())


def begin(operation, using="default"):
    if operation not in OPERATIONS: operation = "unknown"
    principal = OPERATIONS[operation][1]
    # Reserve a sequence by conditional UPDATE, not a read-then-write or a SQLite row-lock assumption.
    for _ in range(16):
        row = _row(principal, using)
        if EbayConnectionHealth.objects.using(using).filter(pk=row.pk, revision=row.revision, connection_id=row.connection_id).update(
            revision=row.revision + 1, updated_at=timezone.now()):
            return Attempt(row.environment, principal, row.connection_id, row.revision + 1, operation, using)
    raise DatabaseError("Health reservation is busy.")


def finish(attempt, *, status=None, failure=None, warnings=None, count=None):
    if attempt is None: return
    for _ in range(16):
        row = EbayConnectionHealth.objects.using(attempt.using).filter(environment=attempt.environment, principal=attempt.principal,
            connection_id=attempt.connection_id).first()
        if not row: return
        operations = deepcopy(row.operations)
        entry = operations.setdefault(attempt.operation, {"last_success": None, "current_failure": None, "warnings": None})
        success = entry["last_success"]
        current_failure = entry["current_failure"]
        newest = max(success["sequence"] if success else 0, current_failure["sequence"] if current_failure else 0)
        if failure:
            if attempt.sequence >= newest:
                entry["current_failure"] = {"sequence": attempt.sequence, "diagnostic": failure}
        else:
            if not success or attempt.sequence >= success["sequence"]:
                entry["last_success"] = {"sequence": attempt.sequence, "time": timezone.now().isoformat(),
                    "http_status": status or 200, "count": count}
            if attempt.sequence >= newest: entry["current_failure"] = None
        if attempt.sequence >= newest: entry["warnings"] = warnings
        if EbayConnectionHealth.objects.using(attempt.using).filter(pk=row.pk, revision=row.revision, connection_id=attempt.connection_id).update(
            operations=operations, revision=row.revision + 1, updated_at=timezone.now()): return
    raise DatabaseError("Health completion is busy.")


def observe_begin(operation):
    try:
        with transaction.atomic(): return begin(operation)
    except DatabaseError:
        logger.warning("eBay diagnostic reservation unavailable; remote outcome handling unchanged.")
        return None


def observe_finish(attempt, **kwargs):
    if attempt and kwargs.get("failure") and kwargs["failure"]["operation"] != attempt.operation:
        kwargs["failure"] = {**kwargs["failure"], "operation": attempt.operation}
    try:
        with transaction.atomic(): finish(attempt, **kwargs)
    except (DatabaseError, ValidationError):
        # Telemetry failure must never transform an acknowledged write into a retry.
        logger.warning("eBay diagnostic completion unavailable; remote outcome handling unchanged.")


def summary():
    from apps.ebay.constants import EBAY_SCOPES, EBAY_MARKETPLACE_ID, EBAY_APP_SCOPE
    env = environment()
    credential = EbayCredential.objects.defer("access_token", "refresh_token").filter(environment=env).first()
    app_token = EbayAppToken.objects.defer("access_token").filter(environment=env).first()
    snapshot = EbayAccountSnapshot.objects.filter(environment=env).first()
    location = MerchantLocation.objects.filter(environment=env).first()
    from apps.listing.models import ListingDraft
    from apps.listing.editor_metadata import METADATA_KEY
    taxonomy_dates = []
    for data in ListingDraft.objects.filter(channel="ebay_au").values_list("channel_data", flat=True):
        categories = data.get(METADATA_KEY, {}).get("categories", {}) if isinstance(data, dict) and isinstance(data.get(METADATA_KEY, {}), dict) else {}
        if isinstance(categories, dict):
            for category in categories.values():
                if isinstance(category, dict) and isinstance(category.get("fetched_at"), str):
                    from django.utils.dateparse import parse_datetime
                    try:
                        stamp = parse_datetime(category["fetched_at"])
                        if stamp and timezone.is_aware(stamp): taxonomy_dates.append(stamp)
                    except ValueError: pass
    rows = {row.principal: row for row in EbayConnectionHealth.objects.filter(environment=env)}
    operations, alerts, checks = [], [], {}
    now = timezone.now()
    for principal in ("seller", "application"):
        state = rows.get(principal)
        checks[principal] = {"started_at": state.check_started_at if state else None,
            "completed_at": state.check_completed_at if state else None, "next_check_at": state.next_check_at if state else None}
        for key, entry in (state.operations if state else {}).items():
            failure = entry["current_failure"]
            display = public_diagnostic(failure["diagnostic"]) if failure else None
            operations.append({"operation": key, "api": OPERATIONS[key][0], "principal": principal,
                "last_success": entry["last_success"], "current_failure": display,
                "warnings": public_diagnostic(entry["warnings"]) if entry["warnings"] else None})
            if display: alerts.append(display)
    token_state = lambda expiry: "unknown" if not expiry else "expired" if expiry <= now else "valid_until_expiry"
    return {"environment": env, "marketplace": EBAY_MARKETPLACE_ID, "connected": credential is not None,
        "account": (credential.ebay_username or credential.ebay_user_id or "Connected account (identity not recorded)") if credential else None,
        "access": {"expires_at": credential.access_token_expires_at if credential else None,
            "state": token_state(credential.access_token_expires_at) if credential else "not_connected"},
        "refresh": {"expires_at": credential.refresh_token_expires_at if credential else None,
            "state": token_state(credential.refresh_token_expires_at) if credential else "not_connected",
            "expiring_soon": bool(credential and credential.refresh_token_expires_at and now < credential.refresh_token_expires_at <= now + timedelta(days=30))},
        "application_access": {"expires_at": app_token.expires_at if app_token else None, "state": token_state(app_token.expires_at) if app_token else "not_yet_checked"},
        "scopes": {"required": list(EBAY_SCOPES), "requested": list(credential.scopes or []) if credential else [],
            "application_required": [EBAY_APP_SCOPE], "grant_status": "not_independently_verified"},
        "snapshots": {"policies": snapshot.fetched_at if snapshot else None, "merchant_location": location.fetched_at if location else None,
            "oldest_saved_category": min(taxonomy_dates) if taxonomy_dates else None, "newest_saved_category": max(taxonomy_dates) if taxonomy_dates else None},
        "checks": checks, "operations": operations, "alerts": alerts,
        "legacy_refresh_failure_unverified": bool(credential and credential.last_refresh_error and not any(r["operation"] == "oauth.refresh" for r in operations)),
        "media_probe": "No stored Media image ID; no upload is performed just to check health.",
        "as_of": now}


def check_connection(*, actor=None):
    """Manual finite GET probes; no scheduling, sync, upload, staging or publish."""
    from apps.ebay import adapters, services
    state = _row("seller")
    now = timezone.now()
    check_id = uuid.uuid4()
    if not EbayConnectionHealth.objects.filter(pk=state.pk, revision=state.revision).filter(
        next_check_at__isnull=True).update(check_id=check_id, check_started_at=now, check_completed_at=None,
            next_check_at=now + CHECK_COOLDOWN, revision=F("revision") + 1, updated_at=now):
        if not EbayConnectionHealth.objects.filter(pk=state.pk, next_check_at__lte=now).update(
            check_id=check_id, check_started_at=now, check_completed_at=None, next_check_at=now + CHECK_COOLDOWN,
            revision=F("revision") + 1, updated_at=now):
            return {"throttled": True, "health": summary()}
    unavailable = set()
    for api, operation in [("Inventory", "inventory.items"), ("Account", "account.payment"),
            ("Fulfilment", "fulfillment.orders"), ("Finances", "finances.transactions"), ("Taxonomy", "taxonomy.tree")]:
        principal = OPERATIONS[operation][1]
        if principal in unavailable: continue
        auth_operation = "oauth.application" if principal == "application" else "oauth.refresh"
        try:
            access = services.get_app_access_token() if principal == "application" else services.get_access_token(actor=actor)
        except Exception as exc:
            observe_finish(observe_begin(auth_operation), failure=safe_exception(exc, auth_operation))
            unavailable.add(principal)
            continue
        ticket = observe_begin(operation)
        try:
            result = adapters.read_connection_probe(api, access_token=access)
        except Exception as exc:
            value = safe_exception(exc, operation)
            # OAuth failures belong to OAuth, not a fabricated successful/failed API probe.
            if value["operation"] == operation: observe_finish(ticket, failure=value)
        else:
            observe_finish(ticket, status=200, count=result)
    completed = timezone.now()
    EbayConnectionHealth.objects.filter(pk=state.pk, connection_id=state.connection_id, check_id=check_id).update(
        check_completed_at=completed, revision=F("revision") + 1, updated_at=completed)
    app = EbayConnectionHealth.objects.filter(environment=state.environment, principal="application").first()
    if app:
        EbayConnectionHealth.objects.filter(pk=app.pk, connection_id=app.connection_id).update(
            check_started_at=now, check_completed_at=completed, updated_at=completed, revision=F("revision") + 1)
    return {"throttled": False, "health": summary()}
