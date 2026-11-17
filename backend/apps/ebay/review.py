"""Manual, immutable reviews of owned listing data and live eBay metadata."""
from copy import copy, deepcopy
from datetime import timedelta
from decimal import Decimal, InvalidOperation
import hashlib
import json
import re
import uuid

from django.utils import timezone

import integrations.ebay as ebay
from apps.ebay.services import get_access_token, get_app_access_token
from apps.ebay.workflow_errors import WorkflowError
from apps.ebay.conditions import CONDITION_ENUMS
from apps.listing.editor import EDITABLE_CHANNEL_FIELDS, LISTING_FIELDS, readiness, sources
from apps.listing.editor_metadata import MARKETPLACE, mapping, policy_options, text
from apps.listing.models import ListingDraft, PublishReview
from apps.listing.readiness import placeholder_checks
from apps.photos.models import PhotoAsset
from integrations.storage import LocalFileStorageAdapter


EPS_LIFETIME = timedelta(days=30)
REVIEW_LIFETIME = timedelta(minutes=10)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def public_data(value):
    if isinstance(value, dict):
        return {str(key): public_data(part) for key, part in value.items()
                if not re.search(r"secret|token|authorization|credential|password|oauth|api.?key|cert.?id", str(key), re.I)}
    if isinstance(value, list):
        return [public_data(part) for part in value]
    return value


def fresh_draft(pk, using="default"):
    return ListingDraft.objects.using(using).select_related("item", "item__category").get(pk=pk)


def photo_state(draft):
    ids = list(map(str, draft.photo_ids or []))
    try:
        for pk in ids:
            uuid.UUID(pk)
    except ValueError:
        return [], [check("photos", "A selected photo ID is invalid.", "photos")]
    assets = {str(row.pk): row for row in PhotoAsset.objects.using(draft._state.db).filter(item_id=draft.item_id, pk__in=ids).select_related("active_derivative")}
    rows, checks = [], []
    storage = LocalFileStorageAdapter()
    for pk in ids:
        row = assets.get(pk)
        if row is None:
            checks.append(check("photos", "A selected photo does not belong to this item or is missing.", "photos"))
            continue
        derivative = row.active_derivative
        derived = derivative and derivative.status == "approved" and derivative.photo_id == row.pk
        path = derivative.fixed_path if derived else row.processed_path
        try:
            content_hash = hashlib.sha256(storage.open(path)).hexdigest() if path else ""
        except (OSError, ValueError):
            content_hash = ""
        if not content_hash:
            checks.append(check("photos", "A selected display photo is unavailable; repair or replace it.", "photos"))
        rows.append({"id": pk, "sha256": content_hash, "derivative": str(derivative.pk) if derived else "", "path": path, "url": storage.url(path) if path else ""})
    if not ids or len(set(ids)) != len(ids):
        checks.append(check("photos", "At least one distinct own photo is required.", "photos"))
    if len(ids) > 24:
        checks.append(check("photos", "Select no more than 24 photos.", "photos"))
    return rows, checks


def field_fingerprint(draft, photos=None):
    photos = photo_state(draft)[0] if photos is None else photos
    return digest({"fields": {key: getattr(draft, key) for key in LISTING_FIELDS},
                   "sku": draft.item.sku, "mapping": {key: mapping(draft.channel_data).get(key, "") for key in sorted(EDITABLE_CHANNEL_FIELDS)},
                   "price_source": mapping(draft.generated_meta).get("price_source"),
                   "photos": [{key: row[key] for key in ("id", "sha256", "derivative")} for row in photos]})


def check(key, message, field="category_id"):
    return {"key": key, "message": message, "field": field, "level": "fail"}


def eps_checks(draft, photos, *, remote_urls=None, now=None):
    from django.utils.dateparse import parse_datetime
    now = now or timezone.now()
    records = mapping(draft.channel_data).get("eps_photos", [])
    issues = {"missing": 0, "unknown upload time": 0, "expired": 0}
    for photo in photos:
        row = next((r for r in records if isinstance(r, dict) and r.get("photo_id") == photo["id"] and r.get("sha256") == photo["sha256"]), {})
        try:
            stamp = parse_datetime(text(row.get("uploaded_at")))
        except (ValueError, TypeError):
            stamp = None
        if row and (not row.get("url") or row.get("missing") or (remote_urls is not None and row.get("url") not in remote_urls)):
            issues["missing"] += 1
        elif not stamp or timezone.is_naive(stamp) or stamp > now:
            issues["unknown upload time"] += 1
        elif stamp <= now - EPS_LIFETIME:
            issues["expired"] += 1
    count = sum(issues.values())
    reasons = "; ".join(f"{reason}: {amount}" for reason, amount in issues.items() if amount)
    return [check("photo_freshness", f"{count} {'photo needs' if count == 1 else 'photos need'} re-uploading ({reasons}). Use Update staged offer.", "staging")] if count else []


def _offer_state(offer):
    return text(offer.get("status")).upper(), text(offer.get("listingId") or mapping(offer.get("listing")).get("listingId"))


def _contains(expected, actual):
    if isinstance(expected, bool) or isinstance(actual, bool):
        return type(expected) is type(actual) and expected == actual
    if isinstance(expected, dict):
        if "currency" in expected and "value" in expected:
            try:
                return isinstance(actual, dict) and expected["currency"] == actual.get("currency") and Decimal(str(expected["value"])) == Decimal(str(actual.get("value")))
            except InvalidOperation:
                return False
        return isinstance(actual, dict) and all(key in actual and _contains(value, actual[key]) for key, value in expected.items())
    if isinstance(expected, list):
        return isinstance(actual, list) and expected == actual
    if isinstance(expected, (Decimal, int)) or isinstance(actual, (Decimal, int)):
        try:
            return Decimal(str(expected)) == Decimal(str(actual))
        except InvalidOperation:
            return False
    return expected == actual


def live_validation(draft, *, actor=None):
    data = mapping(draft.channel_data)
    photos, checks = photo_state(draft)
    # This local gate survives failed metadata reads and is re-run at stage/publish.
    checks.extend({**row.as_dict(), "field": row.key.split(":", 1)[1]} for row in placeholder_checks(draft))
    metadata = None
    offer = inventory_item = None
    raw_policies = {}
    try:
        access = get_access_token(actor=actor)
        taxonomy = ebay.get_ebay_taxonomy_adapter(access_token=get_app_access_token())
        inventory = ebay.get_ebay_inventory_adapter()
        account = ebay.get_ebay_account_adapter()
        category_id = text(data.get("category_id"))
        if category_id:
            node = taxonomy.category_details(category_id=category_id)
            category = {"category": node, "aspects": taxonomy.item_aspects(category_id=category_id) if node.get("is_leaf") is True else [],
                        "condition_policy": taxonomy.item_condition_policy(category_id=category_id),
                        "listing_types": taxonomy.listing_type_policy(category_id=category_id),
                        "fetched_at": timezone.now().isoformat(), "provenance": "Live eBay metadata GETs"}
            condition = mapping(category["condition_policy"])
            if text(condition.get("category_id", category_id)) != category_id or condition.get("marketplace", MARKETPLACE) != MARKETPLACE:
                checks.append(check("condition_id", "Condition policy does not match this category and marketplace.", "condition_id"))
        else:
            category = None
            checks.append(check("category_id", "Choose an eBay leaf category."))
        fetched = timezone.now().isoformat()
        policies = {}
        for kind in ("payment", "fulfillment", "return"):
            raw = account.list_policies(access_token=access, kind=kind)
            policies[kind] = policy_options(kind, raw, fetched)
            chosen = next((row for row in raw if str(row.get(f"{kind}PolicyId")) == text(data.get(f"{kind}_policy_id")) and row.get("marketplaceId", MARKETPLACE) == MARKETPLACE), None)
            if chosen:
                raw_policies[kind] = public_data(chosen)
                for row in policies[kind]:
                    if row["id"] == text(data.get(f"{kind}_policy_id")):
                        row["settings"] = public_data(chosen)
                types = {text(row.get("name")) for row in chosen.get("categoryTypes", []) if isinstance(row, dict)}
                # AU Inventory covers non-vehicle listings. Motor-vehicle-only
                # policies cannot be reused for an Inventory offer.
                if types and "ALL_EXCLUDING_MOTORS_VEHICLES" not in types:
                    checks.append(check(f"{kind}_applicability", "Policy does not apply to this non-vehicle listing category.", f"{kind}_policy_id"))
        if not account.get_policy_optin_status(access_token=access):
            checks.append(check("policies", "Business policies are not enabled for this account.", "payment_policy_id"))
        location_key = text(data.get("merchant_location_key"))
        location = inventory.get_location(access_token=access, merchant_location_key=location_key) if location_key else {}
        enabled = location.get("merchantLocationStatus") == "ENABLED" and (not location.get("merchantLocationKey") or location["merchantLocationKey"] == location_key)
        metadata = {"category_snapshot": category, "category_id": category_id, "category_stale": False,
                    "policies": policies, "policies_stale": False, "policies_fetched_at": fetched,
                    "locations": [{"id": location_key, "verified": enabled, "settings": public_data(location)}] if location_key else []}
        candidate = copy(draft)
        candidate.generated_meta = {**mapping(draft.generated_meta), "listing_defaults_review": []}
        checks.extend(row for row in readiness(candidate, metadata) if row["level"] == "fail")
        values = {text(row.get("name")).casefold(): text(row.get("value")) for row in draft.item_specifics if isinstance(row, dict)}
        for aspect in (category or {}).get("aspects") or []:
            name = text(aspect.get("name"))
            if aspect.get("required") is True and aspect.get("mode") == "SELECTION_ONLY" and values.get(name.casefold()) not in aspect.get("values", []):
                checks.append(check(f"aspect_value:{name}", f"Required specific {name}: choose a valid eBay value.", "item_specifics"))
        conditionless = category and category["condition_policy"].get("required") is False and category["condition_policy"].get("conditions") == []
        if not conditionless and data.get("condition_id") and text(data["condition_id"]) not in CONDITION_ENUMS:
            checks.append(check("condition_mapping", "Selected condition has no verified Inventory API mapping.", "condition_id"))
        if category and category["condition_policy"].get("required") is False and category["condition_policy"].get("conditions") == []:
            pass  # No global grade or manufactured condition gate for a conditionless category.
        from apps.ebay.quantity import quantity_checks
        stock_checks, stock = quantity_checks(draft)
        checks.extend(stock_checks)
        if data.get("offer_id"):
            offer = inventory.get_offer(access_token=access, offer_id=data["offer_id"])
            state, listing_id = _offer_state(offer)
            if state != "UNPUBLISHED" or listing_id:
                checks.append(check("remote_offer", "The offer is published or its state is ambiguous. Reconcile; do not update or publish again."))
            inventory_item = inventory.get_inventory_item(access_token=access, sku=draft.item.sku)
    except Exception as exc:
        # Never copy an exception/provider payload into a response, audit or snapshot.
        from apps.ebay.diagnostics import public_diagnostic, safe_exception
        checks.append({**check("live_metadata", "Live eBay validation is unavailable. Check connection and retry review; saved values are unchanged."),
            "diagnostic": public_diagnostic(safe_exception(exc))})
    from apps.ebay.quantity import quantity_checks
    stock_checks, stock = quantity_checks(draft)
    checks.extend(stock_checks)
    validation_basis = {"stock_fingerprint": stock["fingerprint"], "category": public_data(metadata.get("category_snapshot")) if metadata else None,
                        "policies": raw_policies, "location": public_data(metadata["locations"]) if metadata else None,
                        "remaining": draft.item.quantity_remaining}
    def without_times(value):
        if isinstance(value, dict):
            return {key: without_times(part) for key, part in value.items() if key not in {"fetched_at", "provenance"}}
        if isinstance(value, list):
            return [without_times(part) for part in value]
        return value
    fp = field_fingerprint(draft, photos)
    publish_checks = []
    from apps.ebay.models import EbayListingAllocation
    allocation = EbayListingAllocation.objects.using(draft._state.db or "default").filter(draft=draft, closed_at__isnull=True).first()
    if allocation is None or allocation.allocation_quantity != draft.quantity:
        publish_checks.append(check("allocation_unverified", "Listing allocation is missing or changed. Explicitly Update staged offer and review again.", "staging"))
    if not data.get("offer_id"):
        publish_checks.append(check("stage_required", "Stage this reviewed listing before publishing.", "staging"))
    if draft.staging_state != "verified" or not draft.staged_fingerprint or draft.staged_fingerprint != fp:
        publish_checks.append(check("staged_drift", "Local content is changed or staging is unverified. Explicitly Update staged offer, then review again.", "staging"))
    if offer is not None and inventory_item is not None:
        saved = mapping(data.get("last_payload_snapshot"))
        if not _contains(mapping(saved.get("offer")), offer) or not _contains(mapping(saved.get("inventory_item")), inventory_item):
            publish_checks.append(check("remote_drift", "The remote offer or inventory differs from the staged snapshot. Update staged offer and review again.", "staging"))
        publish_checks.extend(eps_checks(draft, photos, remote_urls=mapping(inventory_item.get("product")).get("imageUrls", [])))
    else:
        publish_checks.extend(eps_checks(draft, photos))
    checks = list({(row["key"], row["field"], row["message"]): row for row in checks}.values())
    return {"metadata": metadata, "checks": checks, "publish_checks": publish_checks, "field_fingerprint": fp, "stock": stock,
            "validation_fingerprint": digest(without_times(validation_basis)), "photos": photos}


def normalized_fees(response, offer_id):
    rows = response.get("feeSummaries") or []
    fees = []
    for row in rows:
        if not isinstance(row, dict) or row.get("marketplaceId") != MARKETPLACE:
            continue
        for fee in row.get("fees") or []:
            amount = mapping(fee.get("amount"))
            try:
                value = Decimal(str(amount["value"]))
                if not value.is_finite() or value < 0:
                    continue
            except (KeyError, InvalidOperation, TypeError):
                continue
            fees.append({"type": text(fee.get("feeType")), "value": str(value), "currency": text(amount.get("currency"))})
    return fees


def prepare_review(draft, *, actor=None, mode="full"):
    draft = fresh_draft(draft.pk, draft._state.db or "default")
    draft.assert_editable()
    if not isinstance(mode, str) or mode not in {"full", "quick"}:
        raise WorkflowError("review_mode", "Choose full or quick review.", status=400)
    result = live_validation(draft, actor=actor)
    fees = []
    offer_id = text(mapping(draft.channel_data).get("offer_id"))
    if offer_id and not result["checks"]:
        try:
            fees = normalized_fees(ebay.get_ebay_inventory_adapter().get_listing_fees(access_token=get_access_token(actor=actor), offer_id=offer_id), offer_id)
            if not fees:
                result["publish_checks"].append(check("fees", "Listing fees were not available; refresh staged review."))
        except Exception:
            result["publish_checks"].append(check("fees", "Listing fee lookup failed; refresh staged review."))
    data = mapping(draft.channel_data)
    snapshot = {"listing": {key: getattr(draft, key) for key in ("title", "description_html", "listing_format", "quantity", "currency")},
                "item_revision": draft.item.updated_at.isoformat(), "remaining_stock": draft.item.quantity_remaining,
                "stock_revision": result["stock"]["stock_revision"], "stock_fingerprint": result["stock"]["fingerprint"],
                "price": str(draft.price) if draft.price is not None else None, "sku": draft.item.sku,
                "specifics": draft.item_specifics,
                "mapping": {key: data.get(key, "") for key in sorted(EDITABLE_CHANNEL_FIELDS)},
                "sources": sources(draft), "metadata": result["metadata"], "photos": result["photos"], "fees": fees,
                "checks": result["checks"], "publish_checks": result["publish_checks"],
                "can_stage": not result["checks"] and mode == "full", "can_publish": not result["checks"] and not result["publish_checks"]}
    review = PublishReview.objects.using(draft._state.db).create(draft=draft, actor=actor if getattr(actor, "pk", None) else None,
        draft_revision=draft.updated_at, field_fingerprint=result["field_fingerprint"], validation_fingerprint=result["validation_fingerprint"],
        staged_fingerprint=draft.staged_fingerprint, offer_id=offer_id, mode=mode, snapshot=public_data(snapshot), expires_at=timezone.now()+REVIEW_LIFETIME)
    return review


def reviewed(draft, review_id, *, actor=None, for_publish=False):
    try:
        if review_id:
            uuid.UUID(str(review_id))
    except (ValueError, TypeError, AttributeError):
        raise WorkflowError("review_required", "Open this listing's review before continuing.", status=400) from None
    review = PublishReview.objects.using(draft._state.db).filter(pk=review_id, draft=draft).first() if review_id else None
    if review is None or review.actor_id != getattr(actor, "pk", None):
        raise WorkflowError("review_required", "Open and review this exact listing before continuing.")
    text_issues = [{**row.as_dict(), "field": row.key.split(":", 1)[1]} for row in placeholder_checks(draft)]
    if text_issues:
        raise WorkflowError("listing_blocked", "Remove the named PLACEHOLDER text before continuing.", checks=text_issues)
    if review.expires_at <= timezone.now() or review.draft_revision != draft.updated_at:
        raise WorkflowError("review_changed", "The reviewed draft changed or review expired. Review again.")
    result = live_validation(draft, actor=actor)
    if review.field_fingerprint != result["field_fingerprint"] or review.validation_fingerprint != result["validation_fingerprint"]:
        raise WorkflowError("review_changed", "Listing values, policy terms, photos or available stock changed. A new review is required.")
    issues = result["checks"] + (result["publish_checks"] if for_publish else [])
    if issues:
        raise WorkflowError("listing_blocked", "Fix the named listing blockers before continuing.", checks=issues)
    if for_publish and not review.snapshot.get("can_publish"):
        raise WorkflowError("review_required", "Review the verified staged offer and its fees first.")
    return review, result


def review_payload(review):
    snapshot = deepcopy(review.snapshot)
    snapshot["photos"] = [{key: value for key, value in row.items() if key != "path"} for row in snapshot.get("photos", [])]
    return {"id": str(review.pk), "draft_revision": review.draft_revision.isoformat(), "mode": review.mode,
            "expires_at": review.expires_at.isoformat(), "offer_id": review.offer_id, **snapshot}
