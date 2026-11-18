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
    return SaleRecord.objects.using(item._state.db or "default").filter(item=item).active()


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
    locked_item = InventoryItem.objects.using(item._state.db or "default").select_for_update().get(pk=item.pk)
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


def create_sale_record(*, data: dict, corrected_from: SaleRecord | None = None) -> SaleRecord:
    using = data["item"]._state.db if data.get("item") is not None else "default"
    using = using or "default"
    from django.core.exceptions import ValidationError as ModelValidationError
    try:
        with transaction.atomic(using=using):
            return _create_sale_record(data=data, corrected_from=corrected_from, using=using)
    except (ValueError, ModelValidationError):
        raise serializers.ValidationError({"fee_inputs": ["Check the complete order, fee inputs and immutable snapshot identity."]}) from None


def _create_sale_record(*, data: dict, corrected_from: SaleRecord | None, using: str) -> SaleRecord:
    data = dict(data)
    fee_context = data.pop("fee_context", None)
    fee_order = data.pop("fee_order", None)
    fee_line_key = data.pop("fee_line_key", None)
    actual_known = data.get("actual_fees_total") is not None and data.get("fee_status", "authoritative") == "authoritative"
    if not actual_known:
        data["actual_fees_total"] = Decimal("0.00")  # Legacy column; the nullable snapshot holds the truth.
        data["fee_status"] = SaleRecord.FeeStatus.ESTIMATED_OR_UNMAPPED
    item = data.get("item")
    if item is None:
        if not data.get("is_external"):
            raise serializers.ValidationError({"item": ["This field is required."]})
        if corrected_from is not None:
            raise serializers.ValidationError(
                {"corrected_from": ["External sale corrections are not supported yet."]}
            )
        sale = SaleRecord.objects.using(using).create(
            **data,
            valuation_snapshot=valuation_snapshot_for(None),
            estimated_fee_snapshot=fee_snapshot_for_sale_price(data["sale_price"]),
        )
        _capture_fee(sale, fee_context, fee_order, fee_line_key, actual_known)
        return sale

    from django.db.models import F
    InventoryItem.objects.using(using).filter(pk=item.pk).update(stock_revision=F("stock_revision") + 1)
    item = InventoryItem.objects.using(using).select_for_update().get(pk=item.pk)
    if item.disposition == InventoryItem.Disposition.SCRAPPED:
        raise serializers.ValidationError(
            {"item": ["Scrapped items are locked and cannot receive new sale records."]}
        )

    if corrected_from is not None:
        corrected_from = (
            SaleRecord.objects.using(using).select_for_update()
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

    sale = SaleRecord.objects.using(using).create(
        **data,
        corrected_from=corrected_from,
        valuation_snapshot=valuation_snapshot_for(item),
        estimated_fee_snapshot=fee_snapshot_for_sale_price(data["sale_price"]),
    )
    _capture_fee(sale, fee_context, fee_order, fee_line_key, actual_known)
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
    # Legacy FeeSchedule is unverified history, never a new-sale default.
    return {"captured_at": timezone.now().isoformat(), "schedule": None,
            "estimated_fees_total": None, "fee_breakdown": {}, "state": "schedule unknown"}


def _capture_fee(sale, context, order, line_key, actual_known):
    from apps.valuation.fee_engine import capture_sale, strict
    if sale.channel != SaleRecord.Channel.EBAY_AU:
        # An eBay calendar is never a fee schedule for a sale on another channel.
        context, order = None, None
    if context is not None:
        strict(context, {"destination_country", "postage", "handling", "marketplace_tax", "other_fee_base", "seller_discount", "buyer_incentives", "promoted_fee", "extra_charges", "ebay_category_id", "ebay_path"}, {"destination_country"})
        category = sale.item.category if sale.item_id and sale.item.category_id else None
        line = {"key": str(sale.pk), "quantity": sale.quantity, "item_total": str(sale.sale_price),
                "category_slug": (category.profile_key or category.slug) if category else "unknown"}
        for k in ("ebay_category_id", "ebay_path"):
            if k in context:
                line[k] = context[k]
        if sale.listing_draft_id and "ebay_category_id" not in line:
            from apps.listing.editor_metadata import cached_category
            draft = sale.listing_draft
            category_id = str((draft.channel_data or {}).get("category_id") or "")
            if category_id:
                saved = cached_category(draft, category_id).get("category", {})
                line["ebay_category_id"] = category_id
                line["ebay_path"] = [str(a["category_id"]) for a in saved.get("ancestors", []) if a.get("category_id")]
        order = {k: v for k, v in context.items() if k not in {"ebay_category_id", "ebay_path"}}
        order.update(sale_date=str(sale.sale_date), lines=[line])
    snapshot = capture_sale(sale, order, line_key=line_key, actual_known=actual_known)
    sale._fee_snapshot_for_display = snapshot


def _decimal_or_none(value) -> str | None:
    return str(value) if value is not None else None
