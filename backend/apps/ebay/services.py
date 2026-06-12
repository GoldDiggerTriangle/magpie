from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import QueryDict
from django.utils import timezone

import integrations.ebay as ebay_integration
from apps.audit.services import record
from apps.ebay.constants import (
    AUDIT_CONNECT_COMPLETED,
    AUDIT_CONNECT_FAILED,
    AUDIT_CONNECT_STARTED,
    AUDIT_DISCONNECT_COMPLETED,
    AUDIT_POLICY_REFRESH_COMPLETED,
    AUDIT_POLICY_REFRESH_FAILED,
    AUDIT_TOKEN_REFRESH_COMPLETED,
    AUDIT_TOKEN_REFRESH_FAILED,
    EBAY_SCOPES,
)
from apps.ebay.fields import ensure_token_key_configured
from apps.ebay.models import EbayAccountSnapshot, EbayCredential, OAuthState


class EbayConnectValidationError(ValidationError):
    pass


@dataclass(frozen=True)
class ConnectionSummary:
    environment: str
    ebay_user_id: str
    ebay_username: str
    scopes: list[str]
    access_token_expires_at: object
    refresh_token_expires_at: object


def start_connect(*, actor=None) -> dict[str, str]:
    ensure_token_key_configured()
    environment = ebay_integration.effective_environment()
    auth_adapter = ebay_integration.get_ebay_auth_adapter()
    state = OAuthState.objects.create()
    try:
        consent_url = auth_adapter.build_consent_url(state=state.state)
    except Exception as exc:
        record(
            actor=actor,
            action=AUDIT_CONNECT_FAILED,
            target_type="ebay_credential",
            payload={"environment": environment, "reason": _safe_error(exc)},
        )
        raise
    record(
        actor=actor,
        action=AUDIT_CONNECT_STARTED,
        target_type="oauth_state",
        target_id=state.id,
        payload={"environment": environment},
    )
    return {"consent_url": consent_url}


def complete_connect(
    *,
    pasted_url: str | None = None,
    code: str | None = None,
    state: str | None = None,
    actor=None,
) -> ConnectionSummary:
    ensure_token_key_configured()
    environment = ebay_integration.effective_environment()
    try:
        parsed_code, parsed_state = _parse_code_and_state(
            pasted_url=pasted_url,
            code=code,
            state=state,
        )
        flow_error: Exception | None = None
        credential = None
        with transaction.atomic():
            oauth_state = _lock_valid_state(parsed_state)
            auth_adapter = ebay_integration.get_ebay_auth_adapter()
            oauth_state.consumed_at = timezone.now()
            oauth_state.save(update_fields=["consumed_at", "updated_at"])
            try:
                token_set = auth_adapter.exchange_code(code=parsed_code)
                if not token_set.refresh_token:
                    raise ebay_integration.EbayUnavailable(
                        "eBay authorization did not return a refresh token."
                    )
            except Exception as exc:
                flow_error = exc
            else:
                # Sprint 6 deliberately uses only sell scopes; Identity API needs
                # commerce.identity.readonly, so it must not block connecting.
                credential, _created = EbayCredential.objects.update_or_create(
                    environment=environment,
                    defaults={
                        "owner": actor if getattr(actor, "is_authenticated", False) else None,
                        "ebay_user_id": "",
                        "ebay_username": "",
                        "scopes": list(EBAY_SCOPES),
                        "refresh_token": token_set.refresh_token,
                        "refresh_token_expires_at": token_set.refresh_expires_at,
                        "access_token": token_set.access_token,
                        "access_token_expires_at": token_set.access_expires_at,
                        "last_refresh_error": "",
                    },
                )
        if flow_error is not None:
            raise flow_error
        assert credential is not None
        record(
            actor=actor,
            action=AUDIT_CONNECT_COMPLETED,
            target_type="ebay_credential",
            target_id=credential.id,
            payload={
                "environment": environment,
                "ebay_username": credential.ebay_username,
                "scopes": credential.scopes,
            },
        )
        return ConnectionSummary(
            environment=credential.environment,
            ebay_user_id=credential.ebay_user_id,
            ebay_username=credential.ebay_username,
            scopes=credential.scopes,
            access_token_expires_at=credential.access_token_expires_at,
            refresh_token_expires_at=credential.refresh_token_expires_at,
        )
    except EbayConnectValidationError as exc:
        record(
            actor=actor,
            action=AUDIT_CONNECT_FAILED,
            target_type="oauth_state",
            payload={
                "environment": environment,
                "state": state or _state_from_pasted_url(pasted_url),
                "reason": _safe_error(exc),
            },
        )
        raise
    except Exception as exc:
        record(
            actor=actor,
            action=AUDIT_CONNECT_FAILED,
            target_type="ebay_credential",
            payload={"environment": environment, "reason": _safe_error(exc)},
        )
        raise


def get_access_token(*, actor=None) -> str:
    ensure_token_key_configured()
    environment = ebay_integration.effective_environment()
    now = timezone.now()
    try:
        credential = EbayCredential.objects.get(environment=environment)
    except EbayCredential.DoesNotExist as exc:
        raise ebay_integration.EbayUnavailable("eBay account is not connected.") from exc

    if _token_valid(credential, now):
        return credential.access_token

    refresh_error: Exception | None = None
    refresh_error_message = ""
    with transaction.atomic():
        credential = EbayCredential.objects.select_for_update().get(pk=credential.pk)
        now = timezone.now()
        if _token_valid(credential, now):
            return credential.access_token
        try:
            token_set = ebay_integration.get_ebay_auth_adapter().refresh(
                refresh_token=credential.refresh_token,
            )
        except Exception as exc:
            refresh_error = exc
            refresh_error_message = _safe_error(exc)
            credential.last_refresh_error = _safe_error(exc)
            credential.save(update_fields=["last_refresh_error", "updated_at"])
        else:
            credential.access_token = token_set.access_token
            credential.access_token_expires_at = token_set.access_expires_at
            if token_set.refresh_token:
                credential.refresh_token = token_set.refresh_token
                credential.refresh_token_expires_at = token_set.refresh_expires_at
            credential.last_refresh_at = timezone.now()
            credential.last_refresh_error = ""
            credential.save(
                update_fields=[
                    "access_token",
                    "access_token_expires_at",
                    "refresh_token",
                    "refresh_token_expires_at",
                    "last_refresh_at",
                    "last_refresh_error",
                    "updated_at",
                ]
            )
    if refresh_error is not None:
        record(
            actor=actor,
            action=AUDIT_TOKEN_REFRESH_FAILED,
            target_type="ebay_credential",
            target_id=credential.id,
            payload={"environment": environment, "reason": refresh_error_message},
        )
        raise ebay_integration.EbayUnavailable(refresh_error_message) from refresh_error
    record(
        actor=actor,
        action=AUDIT_TOKEN_REFRESH_COMPLETED,
        target_type="ebay_credential",
        target_id=credential.id,
        payload={"environment": environment},
    )
    return credential.access_token


def disconnect(*, actor=None) -> None:
    environment = ebay_integration.effective_environment()
    deleted, _ = EbayCredential.objects.filter(environment=environment).delete()
    record(
        actor=actor,
        action=AUDIT_DISCONNECT_COMPLETED,
        target_type="ebay_credential",
        payload={"environment": environment, "deleted": bool(deleted)},
    )


def refresh_account_snapshot(*, actor=None) -> EbayAccountSnapshot:
    environment = ebay_integration.effective_environment()
    try:
        access_token = get_access_token(actor=actor)
        adapter = ebay_integration.get_ebay_account_adapter()
        opted_in = adapter.get_policy_optin_status(access_token=access_token)
        payment = adapter.list_policies(access_token=access_token, kind="payment")
        fulfillment = adapter.list_policies(access_token=access_token, kind="fulfillment")
        returns = adapter.list_policies(access_token=access_token, kind="return")
        snapshot, _created = EbayAccountSnapshot.objects.update_or_create(
            environment=environment,
            defaults={
                "business_policies_opted_in": opted_in,
                "payment_policies": payment,
                "fulfillment_policies": fulfillment,
                "return_policies": returns,
                "fetched_at": timezone.now(),
            },
        )
    except Exception as exc:
        record(
            actor=actor,
            action=AUDIT_POLICY_REFRESH_FAILED,
            target_type="ebay_account_snapshot",
            payload={"environment": environment, "reason": _safe_error(exc)},
        )
        raise

    record(
        actor=actor,
        action=AUDIT_POLICY_REFRESH_COMPLETED,
        target_type="ebay_account_snapshot",
        target_id=snapshot.id,
        payload={
            "environment": environment,
            "opted_in": snapshot.business_policies_opted_in,
            "policy_counts": {
                "payment": len(snapshot.payment_policies),
                "fulfillment": len(snapshot.fulfillment_policies),
                "return": len(snapshot.return_policies),
            },
        },
    )
    return snapshot


def status_summary() -> dict:
    configured = ebay_integration.is_configured()
    environment = ebay_integration.effective_environment()
    credential = (
        EbayCredential.objects.defer("refresh_token", "access_token")
        .filter(environment=environment)
        .first()
    )
    snapshot = EbayAccountSnapshot.objects.filter(environment=environment).first()
    return {
        "configured": configured,
        "environment": environment if configured or credential else "",
        "connected": credential is not None,
        "ebay_username": credential.ebay_username if credential else "",
        "scopes": credential.scopes if credential else [],
        "access_token_expires_at": credential.access_token_expires_at if credential else None,
        "refresh_token_expires_at": credential.refresh_token_expires_at if credential else None,
        "last_refresh_error": credential.last_refresh_error if credential else "",
        "snapshot": _snapshot_payload(snapshot),
    }


def _lock_valid_state(state: str) -> OAuthState:
    try:
        oauth_state = OAuthState.objects.select_for_update().get(state=state)
    except OAuthState.DoesNotExist as exc:
        raise EbayConnectValidationError("Unknown OAuth state.") from exc
    if oauth_state.consumed_at is not None:
        raise EbayConnectValidationError("OAuth state has already been used.")
    if oauth_state.expires_at <= timezone.now():
        raise EbayConnectValidationError("OAuth state has expired.")
    return oauth_state


def _parse_code_and_state(
    *,
    pasted_url: str | None,
    code: str | None,
    state: str | None,
) -> tuple[str, str]:
    if pasted_url:
        query = _query_from_pasted_value(pasted_url)
        params = QueryDict(query)
        code = params.get("code", "")
        state = params.get("state", "")
    if not code or not state:
        raise EbayConnectValidationError("OAuth code and state are required.")
    return code, state


def _state_from_pasted_url(pasted_url: str | None) -> str:
    if not pasted_url:
        return ""
    return QueryDict(_query_from_pasted_value(pasted_url)).get("state", "")


def _query_from_pasted_value(value: str) -> str:
    text = str(value)
    if "?" in text:
        text = text.split("?", 1)[1]
    if "#" in text:
        text = text.split("#", 1)[0]
    return text


def _token_valid(credential: EbayCredential, now) -> bool:
    return bool(
        credential.access_token
        and credential.access_token_expires_at
        and credential.access_token_expires_at > now + timedelta(seconds=60)
    )


def _snapshot_payload(snapshot: EbayAccountSnapshot | None) -> dict:
    if snapshot is None:
        return {
            "opted_in": None,
            "policy_counts": {"payment": 0, "fulfillment": 0, "return": 0},
            "fetched_at": None,
        }
    return {
        "opted_in": snapshot.business_policies_opted_in,
        "policy_counts": {
            "payment": len(snapshot.payment_policies or []),
            "fulfillment": len(snapshot.fulfillment_policies or []),
            "return": len(snapshot.return_policies or []),
        },
        "fetched_at": snapshot.fetched_at,
    }


def _safe_error(exc: Exception) -> str:
    text = str(exc) or exc.__class__.__name__
    replacements = {
        "access_token": "[redacted]",
        "refresh_token": "[redacted]",
        "authorization_code": "[redacted]",
        "token": "credential",
        "Token": "Credential",
        "code": "value",
        "Code": "Value",
    }
    for blocked, replacement in replacements.items():
        text = text.replace(blocked, replacement)
    return text[:300]
