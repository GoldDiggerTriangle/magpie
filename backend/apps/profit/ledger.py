from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from io import StringIO
from statistics import median

from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.inventory.models import InventoryItem
from apps.listing.models import ListingDraft
from apps.profit.models import ProfitSetting, current_profit_setting
from apps.profit.services import PriceBasis, fees_for_seller_receives, normalize_to_seller_receives
from apps.sales.models import SaleRecord


CENT = Decimal("0.01")
PCT = Decimal("0.01")
HUNDRED = Decimal("100")
DEFAULT_STALE_DAYS = 90
RANKING_THRESHOLD = 3
NOT_TAX_ADVICE_LABEL = "Sale records for your accountant - not tax advice."
PROFIT_DAY_TOOLTIP = (
    "days held = max(1, sold date - recorded acquisition date). "
    "profit/day = realised profit / days held. Missing acquisition dates are excluded from velocity."
)
RANKING_TOOLTIP = (
    "STRONG buy-more ranking requires at least 3 known-cost, known-date sales in the category and channel. "
    "Loss-making groups are labelled do not buy more."
)


@dataclass(frozen=True)
class FeeChoice:
    total: Decimal
    provenance: str
    seller_mode: str
    seller_mode_basis: str
    breakdown: dict


def profit_ledger_payload(params) -> dict:
    setting = current_profit_setting()
    stale_days = parse_positive_int(params.get("stale_days"), DEFAULT_STALE_DAYS)
    rows = ledger_rows(setting)
    fy_options = financial_year_options(rows)
    fy = selected_financial_year(params.get("fy"), fy_options)
    fy_rows = rows_for_fy(rows, fy)
    return {
        "currency": "AUD",
        "not_tax_advice_label": NOT_TAX_ADVICE_LABEL,
        "formula_tooltips": {
            "profit": "realised profit = seller-receives revenue - fees - all-in direct costs.",
            "profit_per_day": PROFIT_DAY_TOOLTIP,
            "ranking": RANKING_TOOLTIP,
        },
        "settings": {
            "stale_days": stale_days,
            "ranking_threshold": RANKING_THRESHOLD,
        },
        "summary": summary_for_rows(rows),
        "ledger": rows,
        "aggregates": {
            "by_category": aggregate_rows(rows, "category"),
            "by_channel": aggregate_rows(rows, "channel"),
            "by_source": aggregate_rows(rows, "source_name"),
        },
        "velocity": velocity_summary(rows),
        "cash_lock": cash_lock_payload(stale_days),
        "buy_more": buy_more_payload(rows),
        "financial_years": {
            "options": fy_options,
            "selected": fy,
            "summary": summary_for_rows(fy_rows),
        },
    }


def ledger_csv(params) -> tuple[str, str]:
    rows = ledger_rows(current_profit_setting())
    fy_options = financial_year_options(rows)
    fy = selected_financial_year(params.get("fy"), fy_options)
    fy_rows = rows_for_fy(rows, fy)
    output = StringIO()
    fieldnames = [
        "acquired_date",
        "listed_date",
        "sold_date",
        "item_id",
        "item_sku",
        "title",
        "category",
        "channel",
        "provenance",
        "lot_label",
        "source_name",
        "source_type",
        "seller_mode",
        "revenue",
        "fee_provenance",
        "fee_total",
        "fee_breakdown",
        "acquisition_cost",
        "refurb_cost",
        "inbound_shipping_cost",
        "packaging_cost",
        "postage_label_cost",
        "other_direct_costs",
        "total_costs",
        "realised_profit",
        "days_held",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for row in fy_rows:
        costs = row["cost_components"]
        writer.writerow(
            {
                "acquired_date": row["acquired_date"] or "",
                "listed_date": row["listed_date"] or "",
                "sold_date": row["sold_date"],
                "item_id": row["item_id"] or "",
                "item_sku": row["item_sku"],
                "title": row["title"],
                "category": row["category"],
                "channel": row["channel"],
                "provenance": row["provenance"],
                "lot_label": row["lot_label"] or "",
                "source_name": row["source_name"],
                "source_type": row["source_type"],
                "seller_mode": row["seller_mode"],
                "revenue": row["revenue"],
                "fee_provenance": row["fee_provenance"],
                "fee_total": row["fees"],
                "fee_breakdown": json.dumps(row["fee_breakdown"], sort_keys=True),
                "acquisition_cost": costs["acquisition"],
                "refurb_cost": costs["refurb"],
                "inbound_shipping_cost": costs["inbound_shipping"],
                "packaging_cost": costs["packaging"],
                "postage_label_cost": costs["postage_label"],
                "other_direct_costs": costs["other_direct"],
                "total_costs": row["total_costs"] or "",
                "realised_profit": row["realised_profit"] or "",
                "days_held": row["days_held"] or "",
            }
        )
    filename = f"magpie-profit-ledger-{fy['start_year']}-{fy['end_year']}.csv"
    return filename, output.getvalue()


def ledger_rows(setting: ProfitSetting) -> list[dict]:
    queryset = (
        SaleRecord.objects.active()
        .select_related("item", "item__category", "item__acquisition", "item__lot", "item__lot__source", "item__source", "listing_draft")
        .order_by("-sale_date", "-created_at")
    )
    rows = [serialize_sale_row(sale, setting) for sale in queryset]
    scrapped = (
        InventoryItem.objects.filter(disposition=InventoryItem.Disposition.SCRAPPED, scrapped_at__isnull=False)
        .select_related("category", "acquisition", "lot", "lot__source", "source")
        .prefetch_related("sales")
    )
    rows.extend(serialize_scrapped_row(item) for item in scrapped)
    return sorted(rows, key=lambda row: (row["sold_date"], row["sale_id"]), reverse=True)


def serialize_sale_row(sale: SaleRecord, setting: ProfitSetting) -> dict:
    item = sale.item if sale.item_id else None
    normalized = normalize_to_seller_receives(
        sale.sale_price,
        (sale.channel_data or {}).get("price_basis") or PriceBasis.SELLER_RECEIVES,
    )
    revenue = normalized.seller_receives or money(sale.sale_price)
    fee_choice = fee_choice_for_sale(sale, revenue, setting)
    acquired_on, acquired_basis = acquisition_date_for_item(item)
    listed_on, listed_basis = listed_date_for_sale(sale)
    days_held, days_basis = days_held_for(acquired_on, sale.sale_date)
    costs, cost_state, cost_warning = cost_components_for_sale(sale)
    source = effective_source_for_item(item)
    total_costs = sum(costs.values(), Decimal("0.00")) if cost_state == "known" else None
    realised_profit = money(revenue - fee_choice.total - total_costs) if total_costs is not None else None
    all_in_roi = ratio(realised_profit, total_costs) if realised_profit is not None and total_costs and total_costs > 0 else None
    profit_per_day = money(realised_profit / Decimal(days_held)) if realised_profit is not None and days_held else None
    annualised_roi = (
        (all_in_roi * Decimal("365") / Decimal(days_held)).quantize(PCT, rounding=ROUND_HALF_UP)
        if all_in_roi is not None and days_held
        else None
    )
    return {
        "sale_id": str(sale.id),
        "item_id": str(item.id) if item else None,
        "item_sku": item.sku if item else "external",
        "title": item.title if item else "External sale",
        "category": item.category.name if item and item.category_id else "Uncategorised",
        "category_id": str(item.category_id) if item and item.category_id else None,
        "channel": sale.channel,
        "provenance": sale.provenance,
        "lot_id": str(item.lot_id) if item and item.lot_id else None,
        "lot_label": item.lot.label if item and item.lot_id and item.lot else None,
        "source_id": str(source.id) if source else None,
        "source_name": source.name if source else "Unknown source",
        "source_type": source.type if source else "unknown",
        "seller_mode": fee_choice.seller_mode,
        "seller_mode_basis": fee_choice.seller_mode_basis,
        "quantity": sale.quantity,
        "sold_date": sale.sale_date.isoformat(),
        "acquired_date": acquired_on.isoformat() if acquired_on else None,
        "acquisition_date_basis": acquired_basis,
        "listed_date": listed_on.isoformat() if listed_on else None,
        "listed_date_basis": listed_basis,
        "revenue": str(money(revenue)),
        "price_basis": PriceBasis.SELLER_RECEIVES,
        "fees": str(fee_choice.total),
        "fee_provenance": fee_choice.provenance,
        "fee_breakdown": stringify_money_dict(fee_choice.breakdown),
        "cost_components": stringify_money_dict(costs),
        "cost_state": cost_state,
        "cost_warning": cost_warning,
        "total_costs": str(money(total_costs)) if total_costs is not None else None,
        "realised_profit": str(realised_profit) if realised_profit is not None else None,
        "is_loss": realised_profit is not None and realised_profit < 0,
        "all_in_roi": str(all_in_roi) if all_in_roi is not None else None,
        "days_held": days_held,
        "days_held_basis": days_basis,
        "profit_per_day": str(profit_per_day) if profit_per_day is not None else None,
        "annualised_all_in_roi": str(annualised_roi) if annualised_roi is not None else None,
        "velocity_state": "known" if profit_per_day is not None else ("unknown_date" if days_held is None else "unknown_cost"),
        "detail_url": f"/inventory/{item.id}" if item else "/sales",
    }


def serialize_scrapped_row(item: InventoryItem) -> dict:
    acquired_on, acquired_basis = acquisition_date_for_item(item)
    scrapped_on = item.scrapped_at
    days_held, days_basis = days_held_for(acquired_on, scrapped_on)
    quantity = Decimal(max(item.quantity_remaining, 1))
    source = effective_source_for_item(item)
    costs, cost_state, cost_warning = cost_components_for_scrapped_item(item, quantity)
    total_costs = sum(costs.values(), Decimal("0.00")) if cost_state == "known" else None
    realised_profit = money(Decimal("0.00") - total_costs) if total_costs is not None else None
    profit_per_day = money(realised_profit / Decimal(days_held)) if realised_profit is not None and days_held else None
    all_in_roi = ratio(realised_profit, total_costs) if realised_profit is not None and total_costs and total_costs > 0 else None
    annualised_roi = (
        (all_in_roi * Decimal("365") / Decimal(days_held)).quantize(PCT, rounding=ROUND_HALF_UP)
        if all_in_roi is not None and days_held
        else None
    )
    return {
        "sale_id": f"scrap-{item.id}",
        "item_id": str(item.id),
        "item_sku": item.sku,
        "title": item.title or "Scrapped item",
        "category": item.category.name if item.category_id else "Uncategorised",
        "category_id": str(item.category_id) if item.category_id else None,
        "channel": "scrapped",
        "provenance": "scrapped",
        "lot_id": str(item.lot_id) if item.lot_id else None,
        "lot_label": item.lot.label if item.lot_id and item.lot else None,
        "source_id": str(source.id) if source else None,
        "source_name": source.name if source else "Unknown source",
        "source_type": source.type if source else "unknown",
        "seller_mode": "not_applicable",
        "seller_mode_basis": "scrapped_no_sale",
        "quantity": int(quantity),
        "sold_date": scrapped_on.isoformat(),
        "acquired_date": acquired_on.isoformat() if acquired_on else None,
        "acquisition_date_basis": acquired_basis,
        "listed_date": None,
        "listed_date_basis": "scrapped_no_listing",
        "revenue": "0.00",
        "price_basis": PriceBasis.SELLER_RECEIVES,
        "fees": "0.00",
        "fee_provenance": "actual_recorded",
        "fee_breakdown": {"scrapped": "0.00"},
        "cost_components": stringify_money_dict(costs),
        "cost_state": cost_state,
        "cost_warning": cost_warning,
        "total_costs": str(money(total_costs)) if total_costs is not None else None,
        "realised_profit": str(realised_profit) if realised_profit is not None else None,
        "is_loss": realised_profit is not None and realised_profit < 0,
        "all_in_roi": str(all_in_roi) if all_in_roi is not None else None,
        "days_held": days_held,
        "days_held_basis": days_basis,
        "profit_per_day": str(profit_per_day) if profit_per_day is not None else None,
        "annualised_all_in_roi": str(annualised_roi) if annualised_roi is not None else None,
        "velocity_state": "known" if profit_per_day is not None else ("unknown_date" if days_held is None else "unknown_cost"),
        "detail_url": f"/inventory/{item.id}",
    }


def fee_choice_for_sale(sale: SaleRecord, revenue: Decimal, setting: ProfitSetting) -> FeeChoice:
    seller_mode, seller_mode_basis = seller_mode_for_sale(sale, setting)
    if sale.fee_status == SaleRecord.FeeStatus.AUTHORITATIVE:
        breakdown = dict(sale.actual_fee_breakdown or {})
        if "total" not in breakdown:
            breakdown["total"] = str(money(sale.actual_fees_total))
        return FeeChoice(
            total=money(sale.actual_fees_total),
            provenance="actual_recorded",
            seller_mode=seller_mode,
            seller_mode_basis=seller_mode_basis,
            breakdown=breakdown,
        )
    derived = fees_for_seller_receives(
        seller_receives=revenue,
        seller_mode=seller_mode,
        setting=setting,
    )
    return FeeChoice(
        total=derived.total_seller_fees,
        provenance="schedule_derived",
        seller_mode=seller_mode,
        seller_mode_basis=seller_mode_basis,
        breakdown={
            "seller_final_value_fee": derived.seller_final_value_fee,
            "seller_fixed_fee": derived.seller_fixed_fee,
            "international_delivery_fee": derived.international_delivery_fee,
            "buyer_protection_fee": derived.buyer_protection_fee,
            "buyer_visible_total": derived.buyer_visible_total,
            "basis_note": derived.basis_note,
        },
    )


def seller_mode_for_sale(sale: SaleRecord, setting: ProfitSetting) -> tuple[str, str]:
    valid = {choice[0] for choice in ProfitSetting.SellerMode.choices}
    channel_data = sale.channel_data or {}
    if channel_data.get("seller_mode") in valid:
        return str(channel_data["seller_mode"]), "sale_channel_data"
    snapshot_schedule = (sale.estimated_fee_snapshot or {}).get("schedule") or {}
    if snapshot_schedule.get("seller_mode") in valid:
        return str(snapshot_schedule["seller_mode"]), "sale_fee_snapshot"
    return setting.seller_mode, "current_profit_setting_fallback"


def cost_components_for_sale(sale: SaleRecord) -> tuple[dict[str, Decimal], str, str]:
    item = sale.item if sale.item_id else None
    quantity = Decimal(sale.quantity or 1)
    components = {
        "acquisition": Decimal("0.00"),
        "refurb": Decimal("0.00"),
        "inbound_shipping": Decimal("0.00"),
        "packaging": Decimal("0.00"),
        "postage_label": money(sale.actual_shipping_cost),
        "other_direct": money((sale.channel_data or {}).get("other_direct_costs")),
    }
    if sale.cost_basis_unknown:
        return components, "unknown", "Sale is marked cost-basis unknown."
    if sale.cost_basis_override is not None:
        components["acquisition"] = money(sale.cost_basis_override)
    elif item is None:
        return components, "unknown", "External sale has no inventory cost basis."
    elif item.acquisition_cost is None:
        return components, "unknown", "Acquisition/material cost basis is missing; profit is not computed."
    else:
        components["acquisition"] = per_quantity(item.acquisition_cost, item, quantity)

    if item is not None:
        components["refurb"] = per_quantity(item.refurb_cost, item, quantity)
        components["inbound_shipping"] = per_quantity(item.inbound_shipping_cost, item, quantity)
        packaging = (sale.channel_data or {}).get("packaging_cost")
        components["packaging"] = money(packaging) if packaging not in {None, ""} else per_quantity(item.est_packaging_cost, item, quantity)
    return components, "known", ""


def cost_components_for_scrapped_item(item: InventoryItem, quantity: Decimal) -> tuple[dict[str, Decimal], str, str]:
    components = {
        "acquisition": Decimal("0.00"),
        "refurb": per_quantity(item.refurb_cost, item, quantity),
        "inbound_shipping": per_quantity(item.inbound_shipping_cost, item, quantity),
        "packaging": per_quantity(item.est_packaging_cost, item, quantity),
        "postage_label": Decimal("0.00"),
        "other_direct": Decimal("0.00"),
    }
    if item.acquisition_cost is None:
        return components, "unknown", "Scrapped member has no allocated acquisition cost."
    components["acquisition"] = per_quantity(item.acquisition_cost, item, quantity)
    return components, "known", ""


def cash_cost_for_item(item: InventoryItem) -> tuple[Decimal | None, list[str]]:
    if item.acquisition_cost is None:
        return None, ["acquisition/material cost basis missing"]
    quantity = Decimal(item.quantity_remaining)
    components = [
        per_quantity(item.acquisition_cost, item, quantity),
        per_quantity(item.refurb_cost, item, quantity),
        per_quantity(item.inbound_shipping_cost, item, quantity),
        per_quantity(item.est_packaging_cost, item, quantity),
    ]
    return money(sum(components, Decimal("0.00"))), []


def per_quantity(value, item: InventoryItem, quantity: Decimal) -> Decimal:
    if value in {None, ""}:
        return Decimal("0.00")
    total_quantity = Decimal(max(int(item.quantity_total or 1), 1))
    return money(Decimal(value) / total_quantity * quantity)


def acquisition_date_for_item(item: InventoryItem | None) -> tuple[date | None, str]:
    if item and item.acquisition_id and item.acquisition and item.acquisition.acquired_on:
        return item.acquisition.acquired_on, "recorded_acquisition"
    if item and item.lot_id and item.lot and item.lot.purchase_date:
        return item.lot.purchase_date, "lot_purchase_date"
    return None, "unknown_acquisition_date"


def effective_source_for_item(item: InventoryItem | None):
    if item is None:
        return None
    if item.lot_id and item.lot and item.lot.source_id:
        return item.lot.source
    return item.source


def listed_date_for_sale(sale: SaleRecord) -> tuple[date | None, str]:
    if sale.listing_draft_id and sale.listing_draft:
        return listed_date_for_draft(sale.listing_draft)
    if sale.item_id and sale.item:
        return listed_date_for_item(sale.item)
    return None, "no_listing_record"


def listed_date_for_item(item: InventoryItem) -> tuple[date | None, str]:
    channel_listings = item.channel_listings.all()
    if channel_listings.exists():
        active = [listing for listing in channel_listings if listing.ended_at is None]
        if active:
            earliest = min(active, key=lambda listing: listing.listed_at)
            return earliest.listed_at.date(), "active_channel_listing"
        return None, "channel_listing_records_all_ended"
    draft = (
        item.listing_drafts.filter(Q(status=ListingDraft.Status.PUBLISHED) | Q(channel_data__has_key="listing_id"))
        .order_by("-updated_at")
        .first()
    )
    if draft:
        listed_on, basis = listed_date_for_draft(draft)
        if listed_on:
            return listed_on, basis
        return None, "published_listing_missing_date"
    return None, "no_listed_at_or_publish_record"


def listed_date_for_draft(draft: ListingDraft) -> tuple[date | None, str]:
    data = draft.channel_data or {}
    for key in ["listed_at", "published_at"]:
        parsed = parse_dateish(data.get(key))
        if parsed:
            return parsed, key
    return None, "listing_record_missing_date"


def days_held_for(acquired_on: date | None, sold_on: date) -> tuple[int | None, str]:
    if acquired_on is None:
        return None, "unknown_acquisition_date"
    raw_days = (sold_on - acquired_on).days
    if raw_days <= 0:
        return 1, "recorded_acquisition_guarded_min_1"
    return raw_days, "recorded_acquisition"


def cash_lock_payload(stale_days: int) -> dict:
    buckets = {
        "unlisted": new_cash_bucket("unlisted", "Unlisted"),
        "listed_fresh": new_cash_bucket("listed_fresh", "Listed fresh"),
        "listed_stale": new_cash_bucket("listed_stale", "Listed stale"),
    }
    today = timezone.localdate()
    for item in (
        InventoryItem.objects.select_related("category")
        .exclude(status=InventoryItem.Status.ARCHIVED)
        .prefetch_related("listing_drafts", "channel_listings")
        .order_by("sku")
    ):
        if item.quantity_remaining <= 0:
            continue
        listed_on, listed_basis = listed_date_for_item(item)
        age_days = (today - listed_on).days if listed_on else None
        if listed_on and age_days is not None and age_days >= stale_days:
            bucket_key = "listed_stale"
        elif listed_on:
            bucket_key = "listed_fresh"
        else:
            bucket_key = "unlisted"
        cost, warnings = cash_cost_for_item(item)
        bucket = buckets[bucket_key]
        bucket["item_count"] += 1
        bucket["quantity_remaining"] += item.quantity_remaining
        if cost is None:
            bucket["unknown_cost_item_count"] += 1
        else:
            bucket["cash_locked"] += cost
        bucket["items"].append(
            {
                "item_id": str(item.id),
                "sku": item.sku,
                "title": item.title,
                "category": item.category.name if item.category_id else "Uncategorised",
                "quantity_remaining": item.quantity_remaining,
                "cash_locked": str(cost) if cost is not None else None,
                "cost_state": "known" if cost is not None else "unknown_cost",
                "warnings": warnings,
                "listed_date": listed_on.isoformat() if listed_on else None,
                "listed_age_days": age_days,
                "listed_date_basis": listed_basis,
                "nudge": f"listed {age_days} days - reprice or relist?" if bucket_key == "listed_stale" and age_days is not None else "",
                "hint": "No listed date or publish record; treated as unlisted. Set a listed date if this is listed elsewhere." if bucket_key == "unlisted" else "",
                "detail_url": f"/inventory/{item.id}",
            }
        )
    rows = []
    for bucket in buckets.values():
        rows.append(
            {
                **bucket,
                "cash_locked": str(money(bucket["cash_locked"])),
                "items": bucket["items"],
            }
        )
    return {
        "stale_days": stale_days,
        "buckets": rows,
        "total_known_cash_locked": str(money(sum(Decimal(row["cash_locked"]) for row in rows))),
        "unknown_cost_item_count": sum(row["unknown_cost_item_count"] for row in rows),
        "warning": "Cash-lock totals exclude unknown-cost items, so cash locked may be understated." if any(row["unknown_cost_item_count"] for row in rows) else "",
    }


def new_cash_bucket(bucket_id: str, label: str) -> dict:
    return {
        "id": bucket_id,
        "label": label,
        "cash_locked": Decimal("0.00"),
        "item_count": 0,
        "quantity_remaining": 0,
        "unknown_cost_item_count": 0,
        "items": [],
    }


def buy_more_payload(rows: list[dict]) -> dict:
    grouped: dict[tuple[str, str, str], list[dict]] = {}
    for row in rows:
        if row["realised_profit"] is None or row["profit_per_day"] is None:
            continue
        grouped.setdefault((row["category"], row["channel"], row.get("source_name") or "Unknown source"), []).append(row)
    groups = []
    for (category, channel, source_name), bucket in grouped.items():
        profits = [Decimal(row["realised_profit"]) for row in bucket]
        profit_days = [Decimal(row["profit_per_day"]) for row in bucket]
        days = [Decimal(row["days_held"]) for row in bucket if row["days_held"]]
        newest_sale = max(row["sold_date"] for row in bucket)
        median_profit = money(median(profits))
        median_profit_per_day = money(median(profit_days))
        if len(bucket) < RANKING_THRESHOLD:
            status = "insufficient_data"
            label = f"insufficient data (n = {len(bucket)})"
            recommended = False
        elif median_profit <= 0 or median_profit_per_day <= 0:
            status = "loss_making"
            label = "loss-making - do not buy more"
            recommended = False
        else:
            status = "ranked"
            label = "buy more candidate"
            recommended = True
        groups.append(
            {
                "category": category,
                "channel": channel,
                "source_name": source_name,
                "n": len(bucket),
                "median_profit": str(median_profit),
                "median_profit_per_day": str(median_profit_per_day),
                "median_days_held": int(median(days)) if days else None,
                "newest_sale_date": newest_sale,
                "status": status,
                "label": label,
                "recommended": recommended,
            }
        )
    groups.sort(
        key=lambda row: (
            0 if row["status"] == "ranked" else 1,
            -Decimal(row["median_profit_per_day"]),
            row["category"],
            row["channel"],
        )
    )
    return {
        "threshold": RANKING_THRESHOLD,
        "tooltip": RANKING_TOOLTIP,
        "groups": groups,
        "ranked": [row for row in groups if row["recommended"]],
        "empty": not groups,
    }


def aggregate_rows(rows: list[dict], key: str) -> list[dict]:
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        grouped.setdefault(row[key] or "Uncategorised", []).append(row)
    output = []
    for label, bucket in sorted(grouped.items(), key=lambda item: item[0]):
        output.append({"label": label, **summary_for_rows(bucket)})
    return output


def velocity_summary(rows: list[dict]) -> dict:
    values = [Decimal(row["profit_per_day"]) for row in rows if row["profit_per_day"] is not None]
    return {
        "median_profit_per_day": str(money(median(values))) if values else None,
        "sample_size": len(values),
        "unknown_date_count": sum(1 for row in rows if row["velocity_state"] == "unknown_date"),
        "unknown_cost_count": sum(1 for row in rows if row["velocity_state"] == "unknown_cost"),
        "thin": len(values) < RANKING_THRESHOLD,
        "tooltip": PROFIT_DAY_TOOLTIP,
    }


def summary_for_rows(rows: list[dict]) -> dict:
    revenue = sum_decimal(row["revenue"] for row in rows)
    fees = sum_decimal(row["fees"] for row in rows)
    known_cost_rows = [row for row in rows if row["total_costs"] is not None]
    total_costs = sum_decimal(row["total_costs"] for row in known_cost_rows)
    realised_profit = sum_decimal(row["realised_profit"] for row in known_cost_rows)
    return {
        "sale_count": len(rows),
        "known_profit_sale_count": len(known_cost_rows),
        "unknown_cost_sale_count": len(rows) - len(known_cost_rows),
        "revenue": str(money(revenue)),
        "fees": str(money(fees)),
        "total_costs": str(money(total_costs)),
        "realised_profit": str(money(realised_profit)),
        "loss_sale_count": sum(1 for row in known_cost_rows if Decimal(row["realised_profit"]) < 0),
    }


def financial_year_options(rows: list[dict]) -> list[dict]:
    years = sorted({financial_year_start(date.fromisoformat(row["sold_date"])) for row in rows}, reverse=True)
    if not years:
        years = [financial_year_start(timezone.localdate())]
    return [fy_dict(year) for year in years]


def selected_financial_year(value: str | None, options: list[dict]) -> dict:
    if value:
        digits = [int(part) for part in "".join(char if char.isdigit() else " " for char in value).split()]
        if digits:
            start_year = digits[0]
            return fy_dict(start_year)
    return options[0]


def rows_for_fy(rows: list[dict], fy: dict) -> list[dict]:
    start = date.fromisoformat(fy["start"])
    end = date.fromisoformat(fy["end"])
    return [row for row in rows if start <= date.fromisoformat(row["sold_date"]) <= end]


def financial_year_start(day: date) -> int:
    return day.year if day.month >= 7 else day.year - 1


def fy_dict(start_year: int) -> dict:
    end_year = start_year + 1
    return {
        "id": f"{start_year}-{end_year}",
        "label": f"FY{start_year}-{str(end_year)[-2:]}",
        "start_year": start_year,
        "end_year": end_year,
        "start": f"{start_year}-07-01",
        "end": f"{end_year}-06-30",
    }


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


def parse_positive_int(value, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def money(value) -> Decimal:
    try:
        return Decimal(str(value or "0")).quantize(CENT, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        return Decimal("0.00")


def ratio(numerator: Decimal, denominator: Decimal) -> Decimal | None:
    if denominator == 0:
        return None
    return (numerator / denominator * HUNDRED).quantize(PCT, rounding=ROUND_HALF_UP)


def sum_decimal(values) -> Decimal:
    total = Decimal("0.00")
    for value in values:
        if value in {None, ""}:
            continue
        total += Decimal(str(value))
    return money(total)


def stringify_money_dict(values: dict) -> dict:
    output = {}
    for key, value in values.items():
        output[key] = str(money(value)) if isinstance(value, Decimal) else value
    return output
