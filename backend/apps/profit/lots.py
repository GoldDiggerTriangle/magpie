from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from apps.inventory.models import InventoryItem
from apps.profit.models import Lot


CENT = Decimal("0.01")


@dataclass(frozen=True)
class AllocationLine:
    item: InventoryItem
    amount: Decimal


def money(value) -> Decimal:
    try:
        return Decimal(str(value or "0")).quantize(CENT, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        return Decimal("0.00")


def is_member_locked(item: InventoryItem) -> bool:
    return item.quantity_sold > 0 or item.disposition == InventoryItem.Disposition.SCRAPPED


def member_state(item: InventoryItem) -> str:
    if item.disposition == InventoryItem.Disposition.SCRAPPED:
        return "scrapped"
    if item.quantity_sold > 0:
        return "sold"
    return "unsold"


def lot_queryset():
    return (
        Lot.objects.select_related("source")
        .prefetch_related("items", "items__category", "items__sales")
    )


def lot_summary(lot: Lot) -> dict:
    members = list(
        lot.items.select_related("category", "source", "lot", "lot__source")
        .prefetch_related("sales")
        .order_by("sku")
    )
    total_cost = money(lot.total_cost)
    allocated = money(sum((money(item.acquisition_cost) for item in members if item.acquisition_cost is not None), Decimal("0.00")))
    unallocated = money(total_cost - allocated)
    source = lot.source
    member_rows = [member_payload(item) for item in members]
    unlocked = [item for item in members if not is_member_locked(item)]
    pnl = lot_pnl(lot, member_rows, total_cost, allocated, unallocated)
    return {
        "id": str(lot.id),
        "label": lot.label,
        "purchase_date": lot.purchase_date.isoformat(),
        "total_cost": str(total_cost),
        "source": {"id": str(source.id), "name": source.name, "type": source.type} if source else None,
        "note": lot.note,
        "allocated": str(allocated),
        "unallocated": str(unallocated),
        "is_partially_allocated": allocated != total_cost,
        "is_over_allocated": unallocated < 0,
        "warning": "Over-allocated: member shares exceed the lot total." if unallocated < 0 else "",
        "tally_label": f"allocated ${allocated} of ${total_cost} · remainder ${unallocated}",
        "members": member_rows,
        "proportional_available": bool(unlocked) and all(item.estimated_value and item.estimated_value > 0 for item in unlocked),
        "pnl": pnl,
    }


def member_payload(item: InventoryItem) -> dict:
    locked = is_member_locked(item)
    return {
        "id": str(item.id),
        "sku": item.sku,
        "title": item.title,
        "category": item.category.name if item.category_id else "Uncategorised",
        "state": member_state(item),
        "locked": locked,
        "quantity_sold": item.quantity_sold,
        "acquisition_cost": str(money(item.acquisition_cost)) if item.acquisition_cost is not None else None,
        "estimated_value": str(money(item.estimated_value)) if item.estimated_value is not None else None,
        "scrapped_at": item.scrapped_at.isoformat() if item.scrapped_at else None,
        "detail_url": f"/inventory/{item.id}",
    }


def lot_pnl(lot: Lot, member_rows: list[dict], total_cost: Decimal, allocated: Decimal, unallocated: Decimal) -> dict:
    from apps.profit.ledger import ledger_rows
    from apps.profit.models import current_profit_setting

    item_ids = {row["id"] for row in member_rows}
    rows = [row for row in ledger_rows(current_profit_setting()) if row.get("item_id") in item_ids]
    realised_revenue = money(sum((Decimal(row["revenue"]) for row in rows), Decimal("0.00")))
    realised_profit = money(sum((Decimal(row["realised_profit"]) for row in rows if row["realised_profit"] is not None), Decimal("0.00")))
    remaining_basis = money(
        sum(
            Decimal(row["acquisition_cost"])
            for row in member_rows
            if row["state"] == "unsold" and row["acquisition_cost"] is not None
        )
    )
    recovered = money(realised_revenue)
    return {
        "total_cost": str(total_cost),
        "allocated": str(allocated),
        "unallocated": str(unallocated),
        "realised_revenue": str(realised_revenue),
        "realised_profit": str(realised_profit),
        "remaining_cost_basis": str(remaining_basis),
        "recovered_label": f"recovered ${recovered} of ${total_cost}",
        "is_loss": realised_profit < 0,
        "is_part_allocated": allocated != total_cost,
    }


def _locked_total(members: list[InventoryItem]) -> Decimal:
    return money(sum((money(item.acquisition_cost) for item in members if is_member_locked(item) and item.acquisition_cost is not None), Decimal("0.00")))


def _unlocked_members(lot: Lot) -> list[InventoryItem]:
    members = list(
        InventoryItem.objects.select_for_update()
        .filter(lot=lot)
        .prefetch_related("sales")
        .order_by("sku")
    )
    return [item for item in members if not is_member_locked(item)]


def allocate_to_cent(total: Decimal, members: list[InventoryItem], weights: list[Decimal] | None = None) -> list[AllocationLine]:
    if not members:
        return []
    total = money(total)
    if total < 0:
        total = Decimal("0.00")
    if weights is None:
        base = money(total / Decimal(len(members)))
        amounts = [base for _ in members]
    else:
        weight_total = sum(weights, Decimal("0.00"))
        if weight_total <= 0:
            raise serializers.ValidationError({"detail": "Proportional allocation needs positive estimated values."})
        amounts = [money(total * weight / weight_total) for weight in weights]
    residue = money(total - sum(amounts, Decimal("0.00")))
    amounts[-1] = money(amounts[-1] + residue)
    return [AllocationLine(item=item, amount=amount) for item, amount in zip(members, amounts)]


@transaction.atomic
def allocate_equal(lot: Lot) -> dict:
    locked_lot = Lot.objects.select_for_update().get(pk=lot.pk)
    members = list(
        InventoryItem.objects.select_for_update()
        .filter(lot=locked_lot)
        .prefetch_related("sales")
        .order_by("sku")
    )
    unlocked = [item for item in members if not is_member_locked(item)]
    remaining_to_allocate = money(locked_lot.total_cost - _locked_total(members))
    for line in allocate_to_cent(remaining_to_allocate, unlocked):
        line.item.acquisition_cost = line.amount
        line.item.save(update_fields=["acquisition_cost", "updated_at"])
    return lot_summary(locked_lot)


@transaction.atomic
def allocate_proportional(lot: Lot) -> dict:
    locked_lot = Lot.objects.select_for_update().get(pk=lot.pk)
    members = list(
        InventoryItem.objects.select_for_update()
        .filter(lot=locked_lot)
        .prefetch_related("sales")
        .order_by("sku")
    )
    unlocked = [item for item in members if not is_member_locked(item)]
    weights = [money(item.estimated_value) for item in unlocked]
    if not unlocked or any(weight <= 0 for weight in weights):
        raise serializers.ValidationError({"detail": "Proportional allocation is unavailable until every unlocked member has an estimated value."})
    remaining_to_allocate = money(locked_lot.total_cost - _locked_total(members))
    for line in allocate_to_cent(remaining_to_allocate, unlocked, weights):
        line.item.acquisition_cost = line.amount
        line.item.save(update_fields=["acquisition_cost", "updated_at"])
    return lot_summary(locked_lot)


@transaction.atomic
def allocate_manual(lot: Lot, allocations: list[dict]) -> dict:
    locked_lot = Lot.objects.select_for_update().get(pk=lot.pk)
    members = {
        str(item.id): item
        for item in InventoryItem.objects.select_for_update().filter(lot=locked_lot).prefetch_related("sales")
    }
    for line in allocations:
        item_id = str(line.get("item"))
        if item_id not in members:
            raise serializers.ValidationError({"item": f"{item_id} is not a member of this lot."})
        item = members[item_id]
        if is_member_locked(item):
            continue
        item.acquisition_cost = money(line.get("amount"))
        item.save(update_fields=["acquisition_cost", "updated_at"])
    return lot_summary(locked_lot)


@transaction.atomic
def mark_member_scrapped(item: InventoryItem, *, scrapped_at: date | None = None) -> dict:
    locked = InventoryItem.objects.select_for_update().prefetch_related("sales").get(pk=item.pk)
    if locked.quantity_sold > 0:
        raise serializers.ValidationError({"detail": "Sold members are locked and cannot be marked scrapped."})
    locked.disposition = InventoryItem.Disposition.SCRAPPED
    locked.scrapped_at = scrapped_at or timezone.localdate()
    locked.save(update_fields=["disposition", "scrapped_at", "updated_at"])
    if locked.lot_id:
        return lot_summary(locked.lot)
    return {"item": str(locked.id), "state": member_state(locked)}
