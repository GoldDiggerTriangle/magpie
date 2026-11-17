from __future__ import annotations

from io import BytesIO
import json
import uuid
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.utils import timezone

import integrations.ebay as ebay_integration
from apps.audit.services import record
from apps.ebay.aspects import check_aspects, get_category_condition_policy
from apps.ebay.constants import (
    AUDIT_INVENTORY_ITEM_UPSERTED, AUDIT_MEDIA_UPLOADED, AUDIT_OFFER_CREATED,
    AUDIT_OFFER_UPDATED, AUDIT_OFFER_WITHDRAWN, AUDIT_TAXONOMY_ASPECTS_OVERRIDE,
    CONDITION_MAP, EBAY_MARKETPLACE_ID,
)
from apps.ebay.services import get_access_token
from apps.ebay.review import EPS_LIFETIME, _offer_state, field_fingerprint, fresh_draft, mapping, reviewed, text
from apps.ebay.publish_state import mutable_rows
from apps.ebay.workflow_errors import WorkflowError, provider_error
from apps.ebay.conditions import CONDITION_ENUMS
from apps.inventory.models import InventoryItem
from apps.listing.models import ListingDraft
from apps.photos.models import PhotoAsset
from integrations.storage import LocalFileStorageAdapter


def _stage_progress(pk, attempt, data, *, using, **fields):
    count = ListingDraft.objects.using(using).filter(pk=pk, staging_attempt=attempt, staging_state="in_progress").update(
        channel_data=data, updated_at=timezone.now(), **fields)
    if count != 1:
        raise WorkflowError("staging_changed", "Staging was superseded; do not retry blindly.")
    return count


def recover_stale_staging(pk, using):
    draft = fresh_draft(pk, using)
    if draft.staging_state == "in_progress" and draft.staging_started_at and draft.staging_started_at < timezone.now()-timedelta(minutes=10):
        ListingDraft.objects.using(using).filter(pk=pk, staging_attempt=draft.staging_attempt, staging_state="in_progress").update(
            staging_state="create_unknown" if draft.stage_create_started and not mapping(draft.channel_data).get("offer_id") else "unverified",
            staged_fingerprint="", updated_at=timezone.now())


def stage_draft(draft, *, review_id=None, override_missing_aspects=False, override_reason="", actor=None):
    from django.utils.dateparse import parse_datetime
    using = draft._state.db or "default"
    recover_stale_staging(draft.pk, using)
    draft = fresh_draft(draft.pk, using)
    draft.assert_editable()
    others = ListingDraft.objects.using(using).filter(item_id=draft.item_id, channel=draft.channel).exclude(pk=draft.pk).exclude(status__in=["archived", "published"])
    if any(mapping(row.channel_data).get("offer_id") or row.status in {"publishing", "publish_unknown"} for row in others):
        raise WorkflowError("duplicate_state", "Another draft has unresolved eBay state; resolve it before staging.")
    if override_missing_aspects:
        raise WorkflowError("required_aspects", "Required eBay aspects cannot be overridden.", status=400)
    review, validation = reviewed(draft, review_id, actor=actor)
    if review.mode != "full" or not review.snapshot.get("can_stage"):
        raise WorkflowError("review_required", "Use the full reviewed staging path.")
    attempt = uuid.uuid4()
    from apps.ebay.quantity import reserve_for_stage, stock_basis
    reserve_for_stage(draft, review)
    old_stage_state = draft.staging_state
    if mutable_rows(using).filter(pk=draft.pk, updated_at=review.draft_revision).update(
        staging_state="in_progress", staging_attempt=attempt, staging_started_at=timezone.now(),
        stage_create_started=False, staged_fingerprint="", updated_at=timezone.now()) != 1:
        raise WorkflowError("staging_changed", "Draft changed or another operation is in progress.")
    data = dict(draft.channel_data or {})
    offer_id = text(data.get("offer_id"))
    create_started = False
    try:
        access = get_access_token(actor=actor)
        inventory = ebay_integration.get_ebay_inventory_adapter()
        desired_format = "FIXED_PRICE" if draft.listing_format == "fixed" else "AUCTION"
        remote_offers = {text(row.get("offerId")): row for format_value in ("FIXED_PRICE", "AUCTION")
            for row in inventory.get_offers(access_token=access, sku=draft.item.sku, marketplace_id=EBAY_MARKETPLACE_ID, format=format_value)}
        if any(key != offer_id and (_offer_state(row)[0] != "UNPUBLISHED" or _offer_state(row)[1]) for key, row in remote_offers.items()):
            raise WorkflowError("stock_already_listed", "This SKU has another live (published) or ambiguous eBay offer, including another format. Nothing was staged.")
        if offer_id:
            remote = inventory.get_offer(access_token=access, offer_id=offer_id)
            state, listing_id = _offer_state(remote)
            if state != "UNPUBLISHED" or listing_id or remote.get("sku") != draft.item.sku:
                raise WorkflowError("remote_offer", "Offer is published or ambiguous. Stop; ending a live listing is a separate decision.")
        else:
            matches = list(remote_offers.values())
            if any(row.get("format") != desired_format for row in matches):
                raise WorkflowError("stock_allocated", "Another eBay offer uses this stock in a different format. Resolve it before staging.")
            if len(matches) > 1 or any(_offer_state(row)[0] != "UNPUBLISHED" or _offer_state(row)[1] for row in matches):
                raise WorkflowError("ambiguous_offers", "Existing offers are ambiguous or published. Resolve them before staging.")
            if matches:
                offer_id = text(matches[0].get("offerId"))
                if not offer_id:
                    raise WorkflowError("ambiguous_offers", "Offer identity is missing.")
                data["offer_id"] = offer_id
            elif old_stage_state == "create_unknown":
                raise WorkflowError("create_unknown", "The timed-out createOffer is still unresolved. An empty lookup is not permission to create another offer.")
        photos = validation["photos"]
        previous = data.get("eps_photos") or []
        uploaded = []
        remote_urls = None
        if offer_id:
            try:
                remote_urls = mapping(inventory.get_inventory_item(access_token=access, sku=draft.item.sku).get("product")).get("imageUrls", [])
            except ebay_integration.EbayHttpError as exc:
                if exc.http_status != 404:
                    raise
                remote_urls = []
        media = ebay_integration.get_ebay_media_adapter()
        storage = LocalFileStorageAdapter()
        for photo in photos:
            old = next((row for row in previous if isinstance(row, dict) and row.get("photo_id") == photo["id"] and row.get("sha256") == photo["sha256"]), {})
            try:
                stamp = parse_datetime(text(old.get("uploaded_at")))
            except (ValueError, TypeError):
                stamp = None
            reusable = stamp and not timezone.is_naive(stamp) and timezone.now()-EPS_LIFETIME < stamp <= timezone.now() and old.get("url") and not old.get("missing") and (remote_urls is None or old["url"] in remote_urls)
            if reusable:
                uploaded.append(old)
            else:
                file_obj = BytesIO(storage.open(photo["path"]))
                file_obj.name = draft.item.sku + ".jpg"
                url = media.upload_image(access_token=access, file=file_obj)
                uploaded.append({"photo_id": photo["id"], "sha256": photo["sha256"], "url": url, "uploaded_at": timezone.now().isoformat()})
                record(actor=actor, action=AUDIT_MEDIA_UPLOADED, target_type="listing_draft", target_id=draft.pk, payload={"photo_id": photo["id"], "attempt": str(attempt)}, using=using)
            data["eps_photos"] = list(uploaded)
            _stage_progress(draft.pk, attempt, data, using=using)
        eps_urls = [row["url"] for row in uploaded]
        category = validation["metadata"]["category_snapshot"]
        condition_policy = {**category["condition_policy"], "category_id": text(data.get("category_id")), "marketplace": "EBAY_AU", "fetched_at": category["fetched_at"]}
        inventory_payload = _inventory_item_payload(draft, eps_urls, condition_policy=condition_policy)
        offer_payload = _offer_payload(draft)
        from apps.ebay.adapters import effective_environment
        if stock_basis(draft.item, effective_environment())["fingerprint"] != review.snapshot["stock_fingerprint"]:
            raise WorkflowError("stock_changed", "Stock/orders changed during staging. Review again; no inventory update sent.")
        inventory.upsert_inventory_item(access_token=access, sku=draft.item.sku, payload=inventory_payload)
        record(actor=actor, action=AUDIT_INVENTORY_ITEM_UPSERTED, target_type="listing_draft", target_id=draft.pk, payload={"sku": draft.item.sku, "attempt": str(attempt)}, using=using)
        if offer_id:
            inventory.update_offer(access_token=access, offer_id=offer_id, payload=offer_payload)
        else:
            create_started = True
            _stage_progress(draft.pk, attempt, data, using=using, stage_create_started=True)
            offer_id = inventory.create_offer(access_token=access, payload=offer_payload)
            data["offer_id"] = offer_id
            _stage_progress(draft.pk, attempt, data, using=using)
        if field_fingerprint(fresh_draft(draft.pk, using)) != review.field_fingerprint or stock_basis(draft.item, effective_environment())["fingerprint"] != review.snapshot["stock_fingerprint"]:
            raise WorkflowError("staging_changed", "Photos or listing values changed during staging; update and review again.")
        data.update(eps_image_urls=eps_urls, inventory_item_sku=draft.item.sku, offer_id=offer_id,
            staged_at=timezone.now().isoformat(), last_ebay_error="",
            last_payload_snapshot={"inventory_item": inventory_payload, "offer": offer_payload,
                                   "aspects": {"aspects": category["aspects"], "fetched_at": category["fetched_at"]},
                                   "condition_policy": condition_policy})
        _stage_progress(draft.pk, attempt, data, using=using, status="staged", staging_state="verified",
                        staged_fingerprint=review.field_fingerprint)
        record(actor=actor, action=AUDIT_OFFER_UPDATED if review.offer_id else AUDIT_OFFER_CREATED, target_type="listing_draft", target_id=draft.pk,
               payload={"attempt": str(attempt), "offer_id": offer_id, "photo_count": len(uploaded)}, using=using)
        return fresh_draft(draft.pk, using)
    except Exception as exc:
        error = provider_error(exc, "createOffer" if create_started and not offer_id else "stageOffer")
        data["last_ebay_error"] = {"key": exc.key, "message": exc.message} if isinstance(exc, WorkflowError) else error
        unknown_create = create_started and not offer_id and error["kind"] != "definite_failure"
        if old_stage_state == "create_unknown" and not offer_id:
            unknown_create = True
        ListingDraft.objects.using(using).filter(pk=draft.pk, staging_attempt=attempt, staging_state="in_progress").update(
            channel_data=data, staging_state="create_unknown" if unknown_create else "unverified",
            staged_fingerprint="", updated_at=timezone.now())
        if isinstance(exc, WorkflowError):
            raise
        raise WorkflowError("staging_unverified", "Staging is unverified after a partial/failed operation. Reconcile unknown creation before another create; explicitly update and review again.", status=503, diagnostic=error["diagnostic"]) from None


def withdraw_staged(draft, *, actor=None):
    """Remove an explicitly confirmed unpublished offer; never call withdrawOffer."""
    using = draft._state.db or "default"
    draft = fresh_draft(draft.pk, using)
    draft.assert_editable()
    data = dict(draft.channel_data or {})
    offer_id = text(data.get("offer_id"))
    if not offer_id:
        raise WorkflowError("offer_missing", "No staged offer to remove.")
    attempt = uuid.uuid4()
    if mutable_rows(using).filter(pk=draft.pk, updated_at=draft.updated_at, channel_data__offer_id=offer_id).update(
        staging_state="in_progress", staging_attempt=attempt, staging_started_at=timezone.now(), updated_at=timezone.now()) != 1:
        raise WorkflowError("operation_in_progress", "Another operation won the claim; nothing was removed.")
    try:
        access = get_access_token(actor=actor)
        inventory = ebay_integration.get_ebay_inventory_adapter()
        offer = inventory.get_offer(access_token=access, offer_id=offer_id)
        state, listing_id = _offer_state(offer)
        if state != "UNPUBLISHED" or listing_id or offer.get("sku") != draft.item.sku:
            raise WorkflowError("published_offer", "Offer is published or ambiguous. Stop: ending a live listing is a separate explicit decision.")
        inventory.delete_offer(access_token=access, offer_id=offer_id)
        try:
            inventory.get_offer(access_token=access, offer_id=offer_id)
        except ebay_integration.EbayHttpError as exc:
            if exc.http_status != 404:
                raise
        else:
            raise WorkflowError("removal_unconfirmed", "Offer removal is not confirmed; Archive remains blocked.")
        data.pop("offer_id", None)
        data.pop("staged_at", None)
        data.pop("last_payload_snapshot", None)
        data["eps_image_urls"] = []
        data["eps_photos"] = []
        data["removed_offer_id"] = offer_id
        data["offer_removed_at"] = timezone.now().isoformat()
        data["last_ebay_error"] = ""
        _stage_progress(draft.pk, attempt, data, using=using, staging_state="", staged_fingerprint="", status="ready")
        from apps.ebay.models import EbayListingAllocation
        EbayListingAllocation.objects.using(using).filter(draft=draft, channel_listing__isnull=True, current_attempt__isnull=True).update(closed_at=timezone.now())
        record(actor=actor, action=AUDIT_OFFER_WITHDRAWN, target_type="listing_draft", target_id=draft.pk,
               payload={"attempt": str(attempt), "removed_offer_id": offer_id}, using=using)
        return fresh_draft(draft.pk, using)
    except Exception as exc:
        ListingDraft.objects.using(using).filter(pk=draft.pk, staging_attempt=attempt, staging_state="in_progress").update(
            staging_state="unverified", staged_fingerprint="", updated_at=timezone.now())
        if isinstance(exc, WorkflowError):
            raise
        raise WorkflowError("removal_unconfirmed", "Offer removal could not be confirmed; Archive remains blocked.", status=503) from None


def _locked_draft(pk) -> ListingDraft:
    return (
        ListingDraft.objects.select_related("item", "item__category")
        .prefetch_related("item__photos")
        .get(pk=pk)
    )


def _guard_stageable(draft: ListingDraft) -> dict | None:
    if draft.listing_format not in {ListingDraft.Format.FIXED, ListingDraft.Format.AUCTION}:
        raise ValidationError("Choose a listing format before staging; an empty format is not an auction.")
    if draft.status == ListingDraft.Status.PUBLISHED:
        raise ValidationError("Published drafts cannot be staged again.")
    if draft.item.status in {InventoryItem.Status.SOLD, InventoryItem.Status.ARCHIVED}:
        raise ValidationError("Sold or archived items cannot be staged.")
    conflicting = (
        ListingDraft.objects.filter(
            item=draft.item,
            status__in=[
                ListingDraft.Status.STAGED,
                ListingDraft.Status.PUBLISHED,
                ListingDraft.Status.PUBLISH_FAILED,
            ],
        )
        .exclude(pk=draft.pk)
        .exists()
    )
    if conflicting:
        raise ValidationError("Another draft for this item already has unresolved eBay state.")
    photos = _ordered_photos(draft)
    if not photos:
        raise ValidationError("At least one photo is required before staging.")
    if len(photos) > 24:
        raise ValidationError("eBay staging is limited to 24 photos.")
    required = [
        "category_id",
        "payment_policy_id",
        "fulfillment_policy_id",
        "return_policy_id",
        "merchant_location_key",
    ]
    missing = [key for key in required if not (draft.channel_data or {}).get(key)]
    if missing:
        raise ValidationError(f"Missing eBay staging field(s): {', '.join(missing)}.")
    if not draft.price:
        raise ValidationError("Price is required before staging.")
    if not (draft.channel_data or {}).get("condition_id"):
        policy = get_category_condition_policy(category_id=draft.channel_data["category_id"])
        if not _allows_no_condition(draft, policy):
            raise ValidationError("Missing eBay staging field(s): condition_id.")
        return policy
    return None


def _ordered_photos(draft: ListingDraft) -> list[PhotoAsset]:
    if draft.photo_ids:
        by_id = {str(photo.id): photo for photo in draft.item.photos.all()}
        return [by_id[photo_id] for photo_id in draft.photo_ids if photo_id in by_id]
    return list(draft.item.photos.order_by("order_index", "created_at"))


def _upload_photos(draft: ListingDraft, *, access_token: str, media, actor=None) -> list[str]:
    storage = LocalFileStorageAdapter()
    urls = []
    for index, photo in enumerate(_ordered_photos(draft), start=1):
        key = photo.processed_path or photo.original_path
        data = storage.open(key)
        file_obj = BytesIO(data)
        file_obj.name = f"{draft.item.sku}-{index}.jpg"
        urls.append(media.upload_image(access_token=access_token, file=file_obj))
    record(
        actor=actor,
        action=AUDIT_MEDIA_UPLOADED,
        target_type="listing_draft",
        target_id=draft.id,
        payload={"count": len(urls), "first_url": urls[0] if urls else ""},
    )
    return urls


def _inventory_item_payload(
    draft: ListingDraft,
    eps_urls: list[str],
    *,
    condition_policy: dict | None = None,
) -> dict:
    aspects = {
        str(row.get("name")): [str(row.get("value"))]
        for row in draft.item_specifics or []
        if isinstance(row, dict) and row.get("name") and row.get("value")
    }
    payload = {
        "availability": {
            "shipToLocationAvailability": {
                "quantity": int(draft.quantity),
                "availabilityDistributions": [
                    {
                        "merchantLocationKey": draft.channel_data["merchant_location_key"],
                        "quantity": int(draft.quantity),
                    }
                ],
            }
        },
        "product": {
            "title": draft.title,
            "description": draft.description_html,
            "aspects": aspects,
            "imageUrls": eps_urls,
        },
    }
    # Only explicit category metadata permits omission; an unknown grade is not a condition choice.
    if _allows_no_condition(draft, condition_policy) and not condition_policy["conditions"]:
        pass  # An obsolete local condition cannot create a condition on this category.
    elif (draft.channel_data or {}).get("condition_id"):
        payload["condition"] = _condition_for_draft(draft)["condition"]
    elif not _allows_no_condition(draft, condition_policy):
        raise ValidationError("Missing eBay staging field(s): condition_id.")
    return payload


def _allows_no_condition(draft: ListingDraft, policy: dict | None) -> bool:
    return bool(
        isinstance(policy, dict)
        and policy.get("category_id") == str((draft.channel_data or {}).get("category_id"))
        and policy.get("marketplace") == EBAY_MARKETPLACE_ID
        and policy.get("fetched_at")
        and policy.get("required") is False
        and isinstance(policy.get("conditions"), list)
    )


def _offer_payload(draft: ListingDraft) -> dict:
    channel_data = draft.channel_data or {}
    payload = {
        "sku": draft.item.sku,
        "marketplaceId": EBAY_MARKETPLACE_ID,
        "format": "FIXED_PRICE" if draft.listing_format == ListingDraft.Format.FIXED else "AUCTION",
        "availableQuantity": int(draft.quantity),
        "categoryId": str(channel_data["category_id"]),
        "merchantLocationKey": str(channel_data["merchant_location_key"]),
        "pricingSummary": {
            "price": {
                "currency": draft.currency,
                "value": str(draft.price),
            }
        },
        "listingPolicies": {
            "paymentPolicyId": str(channel_data["payment_policy_id"]),
            "fulfillmentPolicyId": str(channel_data["fulfillment_policy_id"]),
            "returnPolicyId": str(channel_data["return_policy_id"]),
        },
        "includeCatalogProductDetails": False,
    }
    if channel_data.get("listing_duration"):
        payload["listingDuration"] = str(channel_data["listing_duration"])
    return payload


def _recover_unpublished_offer_id(
    *,
    inventory,
    access_token: str,
    draft: ListingDraft,
    offer_payload: dict,
) -> str:
    offers = inventory.get_offers(
        access_token=access_token,
        sku=draft.item.sku,
        marketplace_id=offer_payload["marketplaceId"],
        format=offer_payload["format"],
    )
    candidates = [offer for offer in offers if _is_unpublished_offer(offer)]
    if len(candidates) > 1:
        raise ValidationError("Multiple unpublished eBay offers were found for this SKU and format.")
    if not candidates:
        return ""
    offer_id = candidates[0].get("offerId") or candidates[0].get("offer_id")
    if not offer_id:
        raise ValidationError("An unpublished eBay offer was found but had no offer ID.")
    return str(offer_id)


def _create_or_recover_offer(
    *,
    inventory,
    access_token: str,
    draft: ListingDraft,
    offer_payload: dict,
) -> tuple[str, bool]:
    try:
        return inventory.create_offer(access_token=access_token, payload=offer_payload), False
    except ebay_integration.EbayUnavailable as exc:
        recovered = _offer_id_from_duplicate_error(exc)
        if not recovered:
            raise
        existing = inventory.get_offer(access_token=access_token, offer_id=recovered)
        if not _is_unpublished_offer(existing):
            raise ValidationError(
                "Existing eBay offer is published and cannot be recovered for staging."
            ) from exc
        inventory.update_offer(
            access_token=access_token,
            offer_id=recovered,
            payload=offer_payload,
        )
        return recovered, True


def _is_unpublished_offer(offer: dict) -> bool:
    status = str(offer.get("status") or "").strip().upper()
    if status and status != "UNPUBLISHED":
        return False
    listing = offer.get("listing")
    if isinstance(listing, dict) and listing.get("listingId"):
        return False
    return bool(offer.get("offerId") or offer.get("offer_id"))


def _offer_id_from_duplicate_error(exc: Exception) -> str:
    message = str(exc)
    if "Offer entity already exists" not in message:
        return ""
    try:
        start = message.index("{")
    except ValueError:
        return ""
    try:
        payload = json.loads(message[start:])
    except json.JSONDecodeError:
        return ""
    errors = payload.get("errors") if isinstance(payload, dict) else None
    if not isinstance(errors, list):
        return ""
    for error in errors:
        if not isinstance(error, dict):
            continue
        parameters = error.get("parameters") or []
        if not isinstance(parameters, list):
            continue
        for parameter in parameters:
            if not isinstance(parameter, dict):
                continue
            if str(parameter.get("name")) == "offerId" and parameter.get("value"):
                return str(parameter["value"])
    return ""


def _condition_for_draft(draft: ListingDraft) -> dict:
    override = str((draft.channel_data or {}).get("condition_id") or "")
    if override not in CONDITION_ENUMS:
        raise ValidationError("Selected eBay condition has no verified Inventory API mapping; review condition_id.")
    return {"condition_id": override, "condition": CONDITION_ENUMS[override]}


def _safe_error_payload(exc: Exception):
    from apps.ebay.diagnostics import safe_message
    return {"message": safe_message(exc)}
