from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from rest_framework import serializers

from apps.inventory.models import InventoryItem
from apps.sales.models import SaleRecord, money
from apps.valuation.models import FeeSchedule
from apps.valuation.services import calculate_profit


def active_sales_queryset(item: InventoryItem):
    return SaleRecord.objects.filter(item=item).active()


def active_quantity_sold(item: InventoryItem, *, exclude: SaleRecord | None = None) -> int:
    queryset = active_sales_queryset(item)
    if exclude is not None:
        queryset = queryset.exclude(pk=exclude.pk)
    return int(queryset.aggregate(total=Sum("quantity"))["total"] or 0)


def active_realised_profit(item: InventoryItem) -> Decimal:
    total = Decimal("0.00")
    for sale in active_sales_queryset(item).select_related("item"):
        if sale.realised_profit is not None:
            total += sale.realised_profit
    return total


@transaction.atomic
def recompute_item_sale_status(item: InventoryItem) -> InventoryItem:
    locked_item = InventoryItem.objects.select_for_update().get(pk=item.pk)
    sold = active_quantity_sold(locked_item)
    if sold >= locked_item.quantity_total:
        next_status = InventoryItem.Status.SOLD
    elif sold > 0:
        next_status = InventoryItem.Status.PARTIALLY_SOLD
    elif locked_item.status in {
        InventoryItem.Status.PARTIALLY_SOLD,
        InventoryItem.Status.SOLD,
    }:
        next_status = InventoryItem.Status.CAPTURED
    else:
        return locked_item

    if locked_item.status != next_status:
        locked_item.status = next_status
        locked_item.save(update_fields=["status", "updated_at"])
    return locked_item


@transaction.atomic
def create_sale_record(*, data: dict, corrected_from: SaleRecord | None = None) -> SaleRecord:
    item = data.get("item")
    if item is None:
        if not data.get("is_external"):
            raise serializers.ValidationError({"item": ["This field is required."]})
        if corrected_from is not None:
            raise serializers.ValidationError(
                {"corrected_from": ["External sale corrections are not supported yet."]}
            )
        estimated_fee_snapshot = fee_snapshot_for_sale_price(data["sale_price"])
        if data.get("actual_fees_total") is None:
            data["actual_fees_total"] = money(estimated_fee_snapshot["estimated_fees_total"])
        if not data.get("actual_fee_breakdown"):
            data["actual_fee_breakdown"] = estimated_fee_snapshot.get("fee_breakdown", {})
        return SaleRecord.objects.create(
            **data,
            valuation_snapshot=valuation_snapshot_for(None),
            estimated_fee_snapshot=estimated_fee_snapshot,
        )

    item = InventoryItem.objects.select_for_update().get(pk=item.pk)
    if item.disposition == InventoryItem.Disposition.SCRAPPED:
        raise serializers.ValidationError(
            {"item": ["Scrapped items are locked and cannot receive new sale records."]}
        )

    if corrected_from is not None:
        corrected_from = (
            SaleRecord.objects.select_for_update()
            .get(pk=corrected_from.pk)
        )
        if corrected_from.item_id != item.id:
            raise serializers.ValidationError(
                {"corrected_from": ["Correction must belong to the same item."]}
            )
        if corrected_from.is_superseded:
            raise serializers.ValidationError(
                {"corrected_from": ["This sale record has already been corrected."]}
            )

    quantity = int(data["quantity"])
    sold_without_correction = active_quantity_sold(item, exclude=corrected_from)
    if sold_without_correction + quantity > item.quantity_total:
        remaining = item.quantity_total - sold_without_correction
        raise serializers.ValidationError(
            {"quantity": [f"Quantity exceeds remaining available units ({remaining})."]}
        )

    estimated_fee_snapshot = fee_snapshot_for_sale_price(data["sale_price"])
    if data.get("actual_fees_total") is None:
        data["actual_fees_total"] = money(estimated_fee_snapshot["estimated_fees_total"])
    if not data.get("actual_fee_breakdown"):
        data["actual_fee_breakdown"] = estimated_fee_snapshot.get("fee_breakdown", {})

    sale = SaleRecord.objects.create(
        **data,
        corrected_from=corrected_from,
        valuation_snapshot=valuation_snapshot_for(item),
        estimated_fee_snapshot=estimated_fee_snapshot,
    )
    recompute_item_sale_status(item)
    return sale


def valuation_snapshot_for(item: InventoryItem | None) -> dict:
    if item is None:
        return {
            "captured_at": timezone.now().isoformat(),
            "current_report": None,
            "item_estimated_value": None,
            "currency": "AUD",
        }
    report = (
        item.valuation_reports.filter(is_current=True)
        .select_related("fee_schedule")
        .order_by("-created_at")
        .first()
    )
    if report is None:
        return {
            "captured_at": timezone.now().isoformat(),
            "current_report": None,
            "item_estimated_value": str(item.estimated_value) if item.estimated_value is not None else None,
            "currency": item.currency,
        }
    return {
        "captured_at": timezone.now().isoformat(),
        "current_report": {
            "id": str(report.id),
            "strategy": report.strategy,
            "estimate_low": _decimal_or_none(report.estimate_low),
            "estimate_median": _decimal_or_none(report.estimate_median),
            "estimate_high": _decimal_or_none(report.estimate_high),
            "suggested_price": _decimal_or_none(report.suggested_price),
            "fast_sale_price": _decimal_or_none(report.fast_sale_price),
            "patient_price": _decimal_or_none(report.patient_price),
            "min_acceptable_price": _decimal_or_none(report.min_acceptable_price),
            "currency": report.currency,
            "confidence_score": report.confidence_score,
            "confidence_reason": report.confidence_reason,
            "fee_schedule": str(report.fee_schedule_id) if report.fee_schedule_id else None,
        },
        "item_estimated_value": str(item.estimated_value) if item.estimated_value is not None else None,
        "currency": item.currency,
    }


def fee_snapshot_for_sale_price(sale_price) -> dict:
    schedule = FeeSchedule.objects.filter(is_active=True).order_by("-effective_from").first()
    if schedule is None:
        return {
            "captured_at": timezone.now().isoformat(),
            "schedule": None,
            "estimated_fees_total": "0.00",
            "fee_breakdown": {},
        }
    breakdown = calculate_profit(
        sale_price=sale_price,
        true_cost=Decimal("0.00"),
        schedule=schedule,
        outbound_shipping=Decimal("0.00"),
        packaging=Decimal("0.00"),
    )
    fee_total = money(
        breakdown.final_value_fee
        + breakdown.per_order_fee
        + breakdown.promoted_fee
        + breakdown.gst_on_fees
    )
    return {
        "captured_at": timezone.now().isoformat(),
        "schedule": {
            "id": str(schedule.id),
            "name": schedule.name,
            "effective_from": schedule.effective_from.isoformat(),
            "final_value_pct": str(schedule.final_value_pct),
            "per_order_fee": str(schedule.per_order_fee),
            "promoted_pct": str(schedule.promoted_pct),
            "gst_pct": str(schedule.gst_pct),
        },
        "estimated_fees_total": str(fee_total),
        "fee_breakdown": {
            "final_value_fee": str(breakdown.final_value_fee),
            "per_order_fee": str(breakdown.per_order_fee),
            "promoted_fee": str(breakdown.promoted_fee),
            "gst_on_fees": str(breakdown.gst_on_fees),
        },
    }


def _decimal_or_none(value) -> str | None:
    return str(value) if value is not None else None
