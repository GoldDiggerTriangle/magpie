from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.audit.services import record
from apps.inventory.models import InventoryItem
from apps.listing.draft_status import IN_FLIGHT_DRAFT_STATUSES, TERMINAL_DRAFT_STATUSES
from apps.listing.models import ListingDraft


RELIST_CHANNEL_FIELDS = (
    "category_id", "category_tree_id", "category_name", "condition_id",
    "payment_policy_id", "fulfillment_policy_id", "return_policy_id",
    "merchant_location_key", "listing_duration",
)


def mapping(value):
    return value if isinstance(value, dict) else {}


def present(value):
    return value is not None and bool(str(value).strip())


def completeness_components(draft):
    data = mapping(draft.channel_data)
    snapshot = mapping(data.get("last_payload_snapshot"))
    category = str(data.get("category_id") or "")
    category_matches = bool(category) and str(mapping(snapshot.get("offer")).get("categoryId") or "") == category
    policy = mapping(snapshot.get("condition_policy"))
    condition_unused = (
        category_matches
        and str(policy.get("category_id") or "") == category
        and policy.get("marketplace") == "EBAY_AU"
        and present(policy.get("fetched_at"))
        and policy.get("required") is False
        and policy.get("conditions") == []
    )
    aspects = mapping(snapshot.get("aspects"))
    definitions = aspects.get("aspects")
    known = {
        " ".join(str(row.get("name") or "").lower().split())
        for row in (draft.item_specifics or [])
        if isinstance(row, dict) and present(row.get("name")) and present(row.get("value"))
    }
    metadata_known = (
        category_matches and present(aspects.get("fetched_at"))
        and isinstance(definitions, list)
        and all(isinstance(row, dict) and present(row.get("name")) and isinstance(row.get("required"), bool) for row in definitions)
    )
    required_filled = metadata_known and all(
        " ".join(str(row["name"]).lower().split()) in known
        for row in definitions if row["required"]
    )
    return {
        "title": present(draft.title),
        "category": present(data.get("category_id")),
        "condition": present(data.get("condition_id")) or condition_unused,
        "price": draft.price is not None and draft.price > 0,
        "photos": isinstance(draft.photo_ids, list) and bool(draft.photo_ids),
        "payment": present(data.get("payment_policy_id")),
        "postage": present(data.get("fulfillment_policy_id")),
        "returns": present(data.get("return_policy_id")),
        "location": present(data.get("merchant_location_key")),
        "required_aspects": bool(required_filled),
    }


def draft_summary(draft):
    components = completeness_components(draft)
    return {
        "draft_id": str(draft.pk), "status": draft.status,
        "offer_id": mapping(draft.channel_data).get("offer_id") or None,
        "score": sum(components.values()), "components": components,
        "updated_at": draft.updated_at.isoformat(),
    }


def plan_group(drafts):
    drafts = list(drafts)
    active = [draft for draft in drafts if draft.status not in TERMINAL_DRAFT_STATUSES]
    protected = [draft for draft in drafts if draft.is_read_only]
    candidates = [draft for draft in active if draft not in protected]
    offers = [draft for draft in candidates if present(mapping(draft.channel_data).get("offer_id"))]
    reasons = []
    if any(draft in protected for draft in active):
        reasons.append("active_status_with_published_history")
    if any(draft.status in IN_FLIGHT_DRAFT_STATUSES for draft in candidates):
        reasons.append("publish_outcome_requires_reconciliation")
    if len(offers) > 1:
        reasons.append("multiple_staged_offers")
    keeper = None
    if not reasons and candidates:
        keeper = offers[0] if offers else max(
            candidates, key=lambda draft: (sum(completeness_components(draft).values()), draft.updated_at, draft.pk.int)
        )
    archive = [draft for draft in candidates if keeper is not None and draft.pk != keeper.pk]
    if any(present(mapping(draft.channel_data).get("offer_id")) for draft in archive):
        reasons.append("non_keeper_staged_offer")
        archive = []
    return {
        "item_id": str(drafts[0].item_id), "sku": drafts[0].item.sku,
        "channel": drafts[0].channel,
        "keeper": draft_summary(keeper) if keeper else None,
        "archive": [draft_summary(draft) for draft in sorted(archive, key=lambda draft: draft.pk.int)],
        "active": [draft_summary(draft) for draft in sorted(active, key=lambda draft: draft.pk.int)],
        "preserved_terminal": [str(draft.pk) for draft in protected],
        "unresolved": reasons,
    }


def migration_a_plan():
    groups = {}
    for draft in ListingDraft.objects.select_related("item").order_by("item__sku", "channel", "pk"):
        groups.setdefault((draft.item_id, draft.channel), []).append(draft)
    rows = [plan_group(drafts) for drafts in groups.values()]
    payload = {"version": 1, "groups": rows}
    fingerprint = sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {
        **payload, "fingerprint": fingerprint,
        "archive_count": sum(len(row["archive"]) for row in rows),
        "unresolved_count": sum(bool(row["unresolved"]) for row in rows),
    }


def apply_migration_a(expected_fingerprint):
    with transaction.atomic():
        # Lock the same parent rows as canonical creation; SQLite's write lock is
        # not a substitute for the deferred Migration B uniqueness constraint.
        list(InventoryItem.objects.select_for_update().order_by("pk").values_list("pk", flat=True))
        list(ListingDraft.objects.select_for_update().order_by("pk").values_list("pk", flat=True))
        plan = migration_a_plan()
        if plan["fingerprint"] != expected_fingerprint:
            raise ValidationError("Drafts changed since approval. Run a new Migration A dry run.")
        for group in plan["groups"]:
            for row in group["archive"]:
                changed = ListingDraft.objects.filter(pk=row["draft_id"], status=row["status"]).update(status="archived", updated_at=timezone.now())
                if changed != 1:
                    raise ValidationError("Draft state changed; archival was rolled back.")
                record(
                    actor="migration_a", action="listing.draft.archived",
                    target_type="listing_draft", target_id=row["draft_id"],
                    payload={
                        "item_id": group["item_id"], "channel": group["channel"],
                        "keeper_id": group["keeper"]["draft_id"],
                        "pre_archive_status": row["status"], "offer_id": row["offer_id"],
                        "score": row["score"], "components": row["components"],
                    },
                )
        return plan


def get_or_create_canonical_draft(item, *, channel="ebay_au", create_new):
    with transaction.atomic():
        InventoryItem.objects.select_for_update().get(pk=item.pk)
        drafts = list(ListingDraft.objects.select_related("item").filter(item=item, channel=channel).order_by("pk"))
        if drafts:
            group = plan_group(drafts)
            if group["unresolved"]:
                raise ValidationError("Resolve this item's staged offers/publish outcome before opening a canonical draft.")
            if group["keeper"]:
                return next(draft for draft in drafts if str(draft.pk) == group["keeper"]["draft_id"]), False
        published = [draft for draft in drafts if draft.status == "published"]
        if published:
            source = max(published, key=lambda draft: (draft.updated_at, draft.pk.int))
            fields = {
                field: deepcopy(getattr(source, field))
                for field in (
                    "title", "subtitle", "description_html", "listing_format", "price", "currency",
                    "quantity", "est_shipping_note", "item_specifics", "photo_ids", "include_sku_footer",
                    "boilerplate_id", "title_edited", "description_edited",
                )
            }
            fields["channel_data"] = {key: deepcopy(value) for key, value in mapping(source.channel_data).items() if key in RELIST_CHANNEL_FIELDS}
            fields["generated_meta"] = {"relisted_from": str(source.pk)}
            return ListingDraft.objects.create(item=item, channel=channel, **fields), True
        return create_new(), True
