from __future__ import annotations

from io import BytesIO

from django.core.exceptions import ValidationError
from django.utils import timezone

import integrations.ebay as ebay_integration
from apps.audit.services import record
from apps.ebay.aspects import check_aspects
from apps.ebay.constants import (
    AUDIT_INVENTORY_ITEM_UPSERTED,
    AUDIT_MEDIA_UPLOADED,
    AUDIT_OFFER_CREATED,
    AUDIT_OFFER_UPDATED,
    AUDIT_OFFER_WITHDRAWN,
    AUDIT_TAXONOMY_ASPECTS_OVERRIDE,
    CONDITION_MAP,
    EBAY_MARKETPLACE_ID,
)
from apps.ebay.services import get_access_token
from apps.inventory.models import InventoryItem
from apps.listing.models import ListingDraft
from apps.photos.models import PhotoAsset
from integrations.storage import LocalFileStorageAdapter


def stage_draft(
    draft: ListingDraft,
    *,
    override_missing_aspects=False,
    override_reason: str = "",
    actor=None,
) -> ListingDraft:
    draft = _locked_draft(draft.pk)
    original_status = draft.status
    channel_data = dict(draft.channel_data or {})
    try:
        _guard_stageable(draft)
        aspect_check = check_aspects(draft, actor=actor)
        if aspect_check["missing_required"] and not override_missing_aspects:
            raise ValidationError(
                {
                    "aspects": (
                        "Missing required eBay aspects: "
                        + ", ".join(aspect_check["missing_required"])
                    ),
                    "missing_required": aspect_check["missing_required"],
                }
            )
        if aspect_check["missing_required"]:
            record(
                actor=actor,
                action=AUDIT_TAXONOMY_ASPECTS_OVERRIDE,
                target_type="listing_draft",
                target_id=draft.id,
                payload={
                    "missing_required": aspect_check["missing_required"],
                    "category_id": channel_data.get("category_id"),
                    "reason": override_reason,
                },
            )
        access_token = get_access_token(actor=actor)
        media = ebay_integration.get_ebay_media_adapter()
        inventory = ebay_integration.get_ebay_inventory_adapter()
        eps_urls = _upload_photos(
            draft,
            access_token=access_token,
            media=media,
            actor=actor,
        )
        inventory_payload = _inventory_item_payload(draft, eps_urls)
        inventory.upsert_inventory_item(
            access_token=access_token,
            sku=draft.item.sku,
            payload=inventory_payload,
        )
        record(
            actor=actor,
            action=AUDIT_INVENTORY_ITEM_UPSERTED,
            target_type="listing_draft",
            target_id=draft.id,
            payload={"sku": draft.item.sku, "photo_count": len(eps_urls)},
        )
        offer_payload = _offer_payload(draft)
        offer_id = channel_data.get("offer_id")
        if offer_id:
            inventory.update_offer(
                access_token=access_token,
                offer_id=offer_id,
                payload=offer_payload,
            )
            audit_action = AUDIT_OFFER_UPDATED
        else:
            offer_id = inventory.create_offer(
                access_token=access_token,
                payload=offer_payload,
            )
            audit_action = AUDIT_OFFER_CREATED
        now = timezone.now().isoformat()
        channel_data.update(
            {
                "eps_image_urls": eps_urls,
                "inventory_item_sku": draft.item.sku,
                "offer_id": offer_id,
                "staged_at": now,
                "last_payload_snapshot": {
                    "inventory_item": inventory_payload,
                    "offer": offer_payload,
                    "aspects": aspect_check,
                },
                "last_ebay_error": "",
            }
        )
        draft.channel_data = channel_data
        draft.status = ListingDraft.Status.STAGED
        draft.save(update_fields=["channel_data", "status", "updated_at"])
        record(
            actor=actor,
            action=audit_action,
            target_type="listing_draft",
            target_id=draft.id,
            payload={"offer_id": offer_id, "sku": draft.item.sku},
        )
        return draft
    except Exception as exc:
        channel_data["last_ebay_error"] = _safe_error_payload(exc)
        draft.channel_data = channel_data
        draft.status = (
            ListingDraft.Status.STAGED
            if original_status == ListingDraft.Status.STAGED
            else original_status
        )
        draft.save(update_fields=["channel_data", "status", "updated_at"])
        raise


def withdraw_staged(draft: ListingDraft, *, actor=None) -> ListingDraft:
    draft = _locked_draft(draft.pk)
    if draft.status not in {ListingDraft.Status.STAGED, ListingDraft.Status.PUBLISH_FAILED}:
        raise ValidationError("Only staged or publish-failed drafts can be withdrawn.")
    channel_data = dict(draft.channel_data or {})
    offer_id = channel_data.get("offer_id")
    if not offer_id:
        raise ValidationError("Draft has no unpublished eBay offer to withdraw.")
    access_token = get_access_token(actor=actor)
    ebay_integration.get_ebay_inventory_adapter().withdraw_offer(
        access_token=access_token,
        offer_id=offer_id,
    )
    channel_data.pop("offer_id", None)
    channel_data.pop("staged_at", None)
    channel_data["last_ebay_error"] = ""
    draft.channel_data = channel_data
    draft.status = ListingDraft.Status.READY
    draft.save(update_fields=["channel_data", "status", "updated_at"])
    record(
        actor=actor,
        action=AUDIT_OFFER_WITHDRAWN,
        target_type="listing_draft",
        target_id=draft.id,
        payload={"offer_id": offer_id, "sku": draft.item.sku},
    )
    return draft


def _locked_draft(pk) -> ListingDraft:
    return (
        ListingDraft.objects.select_related("item", "item__category")
        .prefetch_related("item__photos")
        .get(pk=pk)
    )


def _guard_stageable(draft: ListingDraft) -> None:
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
        "condition_id",
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


def _inventory_item_payload(draft: ListingDraft, eps_urls: list[str]) -> dict:
    condition = _condition_for_draft(draft)
    aspects = {
        str(row.get("name")): [str(row.get("value"))]
        for row in draft.item_specifics or []
        if isinstance(row, dict) and row.get("name") and row.get("value")
    }
    return {
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
        "condition": condition["condition"],
        "product": {
            "title": draft.title,
            "description": draft.description_html,
            "aspects": aspects,
            "imageUrls": eps_urls,
        },
    }


def _offer_payload(draft: ListingDraft) -> dict:
    channel_data = draft.channel_data or {}
    return {
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


def _condition_for_draft(draft: ListingDraft) -> dict:
    override = str((draft.channel_data or {}).get("condition_id") or "")
    item_entry = CONDITION_MAP.get(draft.item.condition)
    if item_entry and item_entry["condition_id"] == override:
        return item_entry
    for entry in CONDITION_MAP.values():
        if entry["condition_id"] == override:
            return entry
    return item_entry or CONDITION_MAP["ungraded"]


def _safe_error_payload(exc: Exception):
    message = str(exc) or exc.__class__.__name__
    return {"message": message[:2000]}
