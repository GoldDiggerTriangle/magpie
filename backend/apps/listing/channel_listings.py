from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.inventory.models import InventoryItem
from apps.listing.models import ChannelListing, ListingDraft


CHANNEL_LABELS = {
    ChannelListing.Channel.EBAY: "eBay",
    ChannelListing.Channel.FACEBOOK_MARKETPLACE: "Facebook",
    ChannelListing.Channel.GUMTREE: "Gumtree",
    ChannelListing.Channel.IN_PERSON: "In person",
    ChannelListing.Channel.OTHER: "Other",
}


@dataclass(frozen=True)
class SeedResult:
    seeded: int
    existing: int
    skipped_ambiguous: int
    skipped_missing_date: int


def seed_ebay_channel_listings() -> SeedResult:
    candidates = list(
        ListingDraft.objects.select_related("item")
        .filter(Q(status=ListingDraft.Status.PUBLISHED) | Q(channel_data__has_key="listing_id"))
        .exclude(channel_data__listing_id="")
        .order_by("item_id", "-updated_at")
    )
    by_item = defaultdict(list)
    for draft in candidates:
        if (draft.channel_data or {}).get("listing_id"):
            by_item[draft.item_id].append(draft)

    seeded = existing = skipped_ambiguous = skipped_missing_date = 0
    with transaction.atomic():
        for drafts in by_item.values():
            if len(drafts) != 1:
                skipped_ambiguous += len(drafts)
                continue
            draft = drafts[0]
            listed_at = listed_at_for_draft(draft)
            if listed_at is None:
                skipped_missing_date += 1
                continue
            _listing, created = ChannelListing.objects.get_or_create(
                source_listing_draft=draft,
                defaults={
                    "item": draft.item,
                    "channel": ChannelListing.Channel.EBAY,
                    "listed_at": listed_at,
                    "note": "Seeded from local Magpie eBay publish record.",
                },
            )
            if created:
                seeded += 1
            else:
                existing += 1
    return SeedResult(
        seeded=seeded,
        existing=existing,
        skipped_ambiguous=skipped_ambiguous,
        skipped_missing_date=skipped_missing_date,
    )


def item_listing_state(item: InventoryItem) -> dict:
    if item.quantity_remaining <= 0:
        active = list(active_channel_listings(item))
        return {
            "state": "take_down_required" if active else "sold_out_clear",
            "message": take_down_message(active) if active else "",
            "active_listings": active,
            "quantity_sold": item.quantity_sold,
            "quantity_remaining": item.quantity_remaining,
            "quantity_total": item.quantity_total,
        }
    if item.quantity_sold > 0:
        return {
            "state": "partial_quantity",
            "message": f"sold {item.quantity_sold} of {item.quantity_total} - listings still valid.",
            "active_listings": list(active_channel_listings(item)),
            "quantity_sold": item.quantity_sold,
            "quantity_remaining": item.quantity_remaining,
            "quantity_total": item.quantity_total,
        }
    return {
        "state": "available",
        "message": "",
        "active_listings": list(active_channel_listings(item)),
        "quantity_sold": item.quantity_sold,
        "quantity_remaining": item.quantity_remaining,
        "quantity_total": item.quantity_total,
    }


def take_down_message(listings) -> str:
    labels = ", ".join(CHANNEL_LABELS.get(listing.channel, listing.get_channel_display()) for listing in listings)
    return f"Still listed on: {labels} - take them down."


def active_channel_listings(item: InventoryItem):
    return item.channel_listings.filter(ended_at__isnull=True).order_by("channel", "listed_at")


def take_down_items_queryset():
    return (
        InventoryItem.objects.select_related("category")
        .prefetch_related("channel_listings", "sales")
        .filter(channel_listings__ended_at__isnull=True)
        .distinct()
    )


def take_down_checklist_items() -> list[InventoryItem]:
    return [item for item in take_down_items_queryset() if item.quantity_remaining <= 0]


def listed_at_for_draft(draft: ListingDraft):
    data = draft.channel_data or {}
    for key in ["listed_at", "published_at"]:
        parsed = parse_dateish(data.get(key))
        if parsed:
            return timezone.make_aware(datetime.combine(parsed, datetime.min.time()))
    return None


def parse_dateish(value) -> date | None:
    if not value:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    text = str(value)
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        parsed = parse_datetime(text)
        if parsed:
            return timezone.localdate(parsed)
    return None
