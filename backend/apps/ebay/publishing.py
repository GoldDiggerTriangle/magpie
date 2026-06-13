from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

import integrations.ebay as ebay_integration
from apps.audit.services import record
from apps.ebay.aspects import check_aspects
from apps.ebay.constants import (
    AUDIT_PUBLISH_ATTEMPTED,
    AUDIT_PUBLISH_FAILED,
    AUDIT_PUBLISH_SUCCEEDED,
)
from apps.ebay.services import get_access_token
from apps.inventory.models import InventoryItem
from apps.listing.models import ListingDraft


def staged_review(draft: ListingDraft, *, actor=None) -> dict:
    if draft.status != ListingDraft.Status.STAGED:
        raise ValidationError("Only staged drafts can be reviewed for publish.")
    offer_id = (draft.channel_data or {}).get("offer_id")
    if not offer_id:
        raise ValidationError("Draft has no staged eBay offer.")
    access_token = get_access_token(actor=actor)
    offer = ebay_integration.get_ebay_inventory_adapter().get_offer(
        access_token=access_token,
        offer_id=offer_id,
    )
    aspect_check = check_aspects(draft, actor=actor)
    snapshot = {
        "offer_id": offer_id,
        "sku": offer.get("sku") or draft.item.sku,
        "title": _nested(offer, "listingDescription") or draft.title,
        "category_id": offer.get("categoryId") or (draft.channel_data or {}).get("category_id"),
        "category_name": (draft.channel_data or {}).get("category_name", ""),
        "condition": _nested(offer, "condition") or (draft.channel_data or {}).get("condition_id"),
        "price": _nested(offer, "pricingSummary", "price", "value") or str(draft.price),
        "currency": _nested(offer, "pricingSummary", "price", "currency") or draft.currency,
        "quantity": offer.get("availableQuantity") or draft.quantity,
        "format": offer.get("format") or draft.listing_format,
        "payment_policy_id": _nested(offer, "listingPolicies", "paymentPolicyId")
        or (draft.channel_data or {}).get("payment_policy_id"),
        "fulfillment_policy_id": _nested(offer, "listingPolicies", "fulfillmentPolicyId")
        or (draft.channel_data or {}).get("fulfillment_policy_id"),
        "return_policy_id": _nested(offer, "listingPolicies", "returnPolicyId")
        or (draft.channel_data or {}).get("return_policy_id"),
        "merchant_location_key": offer.get("merchantLocationKey")
        or (draft.channel_data or {}).get("merchant_location_key"),
        "photo_count": len((draft.channel_data or {}).get("eps_image_urls") or []),
        "aspect_warnings": aspect_check,
    }
    channel_data = dict(draft.channel_data or {})
    channel_data["last_offer_snapshot"] = snapshot
    draft.channel_data = channel_data
    draft.save(update_fields=["channel_data", "updated_at"])
    return snapshot


def publish_draft(draft: ListingDraft, *, confirm_sku: str, actor=None) -> ListingDraft:
    failure = None
    with transaction.atomic():
        draft = (
            ListingDraft.objects.select_for_update()
            .select_related("item")
            .get(pk=draft.pk)
        )
        channel_data = dict(draft.channel_data or {})
        if channel_data.get("listing_id"):
            raise ValidationError("Draft already has a published eBay listing.")
        if draft.status == ListingDraft.Status.PUBLISHED:
            raise ValidationError("Published drafts cannot be published again.")
        if draft.status != ListingDraft.Status.STAGED:
            raise ValidationError("Only staged drafts can be published.")
        if confirm_sku != draft.item.sku:
            raise ValidationError("Type the exact SKU to publish this draft.")
        offer_id = channel_data.get("offer_id")
        if not offer_id:
            raise ValidationError("Draft has no staged eBay offer.")

        record(
            actor=actor,
            action=AUDIT_PUBLISH_ATTEMPTED,
            target_type="listing_draft",
            target_id=draft.id,
            payload={"offer_id": offer_id, "sku": draft.item.sku},
        )
        access_token = get_access_token(actor=actor)
        try:
            listing_id = ebay_integration.get_ebay_inventory_adapter().publish_offer(
                access_token=access_token,
                offer_id=offer_id,
            )
        except Exception as exc:
            channel_data["last_ebay_error"] = _safe_error_payload(exc)
            draft.channel_data = channel_data
            draft.status = ListingDraft.Status.PUBLISH_FAILED
            draft.save(update_fields=["channel_data", "status", "updated_at"])
            record(
                actor=actor,
                action=AUDIT_PUBLISH_FAILED,
                target_type="listing_draft",
                target_id=draft.id,
                payload={"offer_id": offer_id, "reason": str(exc)[:1000]},
            )
            failure = exc
        else:
            now = timezone.now().isoformat()
            channel_data.update(
                {
                    "listing_id": listing_id,
                    "published_at": now,
                    "last_ebay_error": "",
                }
            )
            draft.channel_data = channel_data
            draft.status = ListingDraft.Status.PUBLISHED
            draft.item.status = InventoryItem.Status.LISTED
            draft.item.save(update_fields=["status", "updated_at"])
            draft.save(update_fields=["channel_data", "status", "updated_at"])
            record(
                actor=actor,
                action=AUDIT_PUBLISH_SUCCEEDED,
                target_type="listing_draft",
                target_id=draft.id,
                payload={"offer_id": offer_id, "listing_id": listing_id, "sku": draft.item.sku},
            )
    if failure:
        raise failure
    return draft


def _nested(data: dict, *keys):
    current = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _safe_error_payload(exc: Exception):
    return {"message": (str(exc) or exc.__class__.__name__)[:2000]}
