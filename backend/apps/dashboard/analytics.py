from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from statistics import median
from uuid import UUID

from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone

from apps.catalog.models import ProductCategory
from apps.dashboard.models import KPI_TILE_CATALOG
from apps.ebay.models import EbayOrderStaging
from apps.inventory.models import InventoryItem
from apps.listing.channel_listings import take_down_checklist_items
from apps.listing.models import ListingDraft
from apps.sales.models import SaleRecord, money


ZERO = Decimal("0.00")
AGE_BUCKETS = [
    ("0_30", "0-30 days", 0, 30),
    ("31_90", "31-90 days", 31, 90),
    ("91_180", "91-180 days", 91, 180),
    ("180_plus", "180+ days", 181, None),
]


@dataclass(frozen=True)
class AnalyticsFilters:
    start: date | None
    end: date | None
    category_ids: tuple[str, ...]
    channel: str
    unknown_mode: str
    range_label: str


def parse_filters(params) -> AnalyticsFilters:
    today = timezone.localdate()
    range_key = params.get("range") or params.get("time_range") or "12m"
    start = None
    end = today
    if range_key == "this_month":
        start = today.replace(day=1)
    elif range_key == "3m":
        start = _month_start(today, 2)
    elif range_key == "6m":
        start = _month_start(today, 5)
    elif range_key == "12m":
        start = _month_start(today, 11)
    elif range_key == "custom":
        start = _parse_date(params.get("start"))
        end = _parse_date(params.get("end")) or today
    elif range_key == "all":
        start = None
        end = None
    else:
        range_key = "12m"
        start = _month_start(today, 11)

    category_ids = _list_param(params, "category")
    channel = params.get("channel") or "all"
    if channel not in {"all", "ebay_au", "manual", "other", "external"}:
        channel = "all"
    unknown_mode = params.get("unknown") or params.get("unknown_mode") or "honest"
    if unknown_mode not in {"honest", "hide", "include"}:
        unknown_mode = "honest"
    return AnalyticsFilters(
        start=start,
        end=end,
        category_ids=tuple(category_ids),
        channel=channel,
        unknown_mode=unknown_mode,
        range_label=range_key,
    )


def build_summary(filters: AnalyticsFilters) -> dict:
    sales = filtered_sales(filters)
    known_sales = known_profit_sales(sales)
    linked_sales = sales.filter(item__isnull=False)
    unknown_count = sales.filter(cost_basis_unknown=True).count()
    revenue = sum_money(sales, "sale_price")
    known_revenue = sum_money(known_sales, "sale_price")
    net_proceeds = sum_sale_net(sales)
    realised_profit = sum_sale_profit(known_sales)
    sold_quantity = int(sales.aggregate(total=Sum("quantity"))["total"] or 0)
    linked_sold_quantity = int(linked_sales.aggregate(total=Sum("quantity"))["total"] or 0)
    available_units = inventory_remaining_units(filters)
    sell_through = _percent(
        Decimal(linked_sold_quantity),
        Decimal(linked_sold_quantity + available_units),
    )
    avg_margin = _percent(realised_profit, known_revenue)
    avg_time_to_sale = average_time_to_sale(known_sales)
    inventory_cost = available_inventory_cost(filters)
    inventory_value = available_inventory_value(filters)
    aged_count = aged_inventory_count(filters)
    staging_count = EbayOrderStaging.objects.filter(
        status=EbayOrderStaging.Status.PENDING
    ).count()
    take_down_count = len(take_down_checklist_items())

    tiles = {
        "realised_profit": tile_value(
            "realised_profit",
            realised_profit,
            secondary=_unknown_secondary(unknown_count),
            excluded_count=unknown_count,
        ),
        "gross_revenue": tile_value("gross_revenue", revenue),
        "net_proceeds": tile_value("net_proceeds", net_proceeds),
        "items_sold": tile_value("items_sold", sold_quantity),
        "sell_through": tile_value("sell_through", sell_through),
        "avg_realised_margin": tile_value(
            "avg_realised_margin",
            avg_margin,
            secondary=_unknown_secondary(unknown_count),
            excluded_count=unknown_count,
        ),
        "avg_time_to_sale": tile_value("avg_time_to_sale", avg_time_to_sale),
        "inventory_cost_basis": tile_value("inventory_cost_basis", inventory_cost),
        "estimated_inventory_value": tile_value("estimated_inventory_value", inventory_value),
        "aged_inventory_count": tile_value("aged_inventory_count", aged_count),
        "unresolved_ebay_staging_count": tile_value(
            "unresolved_ebay_staging_count",
            staging_count,
        ),
        "cost_basis_unknown_sales_count": tile_value(
            "cost_basis_unknown_sales_count",
            unknown_count,
        ),
    }
    return {
        "currency": "AUD",
        "filters": serialize_filters(filters),
        "tiles": tiles,
        "action_counts": {
            "unresolved_ebay_staging": staging_count,
            "cost_basis_unknown_sales": unknown_count,
            "listing_opportunities": len(build_listing_opportunities(filters)["items"]),
            "take_down_checklists": take_down_count,
        },
        "sample": {
            "sales": sales.count(),
            "known_profit_sales": known_sales.count(),
            "linked_sales": linked_sales.count(),
        },
    }


def build_pnl(filters: AnalyticsFilters) -> dict:
    sales = filtered_sales(filters)
    net_by_month = {}
    for row in (
        sales.annotate(month=TruncMonth("sale_date"))
        .values("month")
        .annotate(
            sale_price=Sum("sale_price"),
            fees=Sum("actual_fees_total"),
            shipping=Sum("actual_shipping_cost"),
            quantity=Sum("quantity"),
        )
    ):
        month = row["month"]
        month_date = month.date() if hasattr(month, "date") else month
        net_by_month[month_date.isoformat()] = row
    profit_by_month = defaultdict(lambda: ZERO)
    unknown_by_month = defaultdict(int)
    for sale in sales.select_related("item").order_by("sale_date"):
        key = sale.sale_date.replace(day=1).isoformat()
        if sale.cost_basis_unknown:
            unknown_by_month[key] += 1
            continue
        profit = sale.realised_profit
        if profit is not None:
            profit_by_month[key] += profit

    months = sorted(set(net_by_month) | set(profit_by_month) | set(unknown_by_month))
    series = []
    for month in months:
        row = net_by_month.get(month, {})
        net = money(
            (row.get("sale_price") or ZERO)
            - (row.get("fees") or ZERO)
            - (row.get("shipping") or ZERO)
        )
        series.append(
            {
                "month": month,
                "realised_profit": money(profit_by_month[month]),
                "net_proceeds": net,
                "gross_revenue": money(row.get("sale_price") or ZERO),
                "quantity": int(row.get("quantity") or 0),
                "unknown_cost_sales": unknown_by_month[month],
            }
        )
    return {
        "currency": "AUD",
        "series": [_money_dict(row) for row in series],
        "small_sample": sales.count() > 0 and sales.count() < 5,
        "empty": sales.count() == 0,
    }


def build_by_category(filters: AnalyticsFilters) -> dict:
    categories = ProductCategory.objects.all().order_by("name")
    if filters.category_ids:
        categories = categories.filter(id__in=filters.category_ids)
    rows = []
    sales = filtered_sales(filters).filter(item__category__isnull=False)
    for category in categories:
        cat_sales = sales.filter(item__category=category)
        known = known_profit_sales(cat_sales)
        revenue = sum_money(cat_sales, "sale_price")
        known_revenue = sum_money(known, "sale_price")
        profit = sum_sale_profit(known)
        sold = int(cat_sales.aggregate(total=Sum("quantity"))["total"] or 0)
        available = inventory_remaining_units(filters, category=category)
        if revenue == ZERO and available == 0:
            continue
        rows.append(
            {
                "category_id": str(category.id),
                "category": category.name,
                "gross_revenue": revenue,
                "realised_profit": profit,
                "margin": _percent(profit, known_revenue),
                "sell_through": _percent(Decimal(sold), Decimal(sold + available)),
                "items_sold": sold,
                "available_units": available,
                "unknown_cost_sales": cat_sales.filter(cost_basis_unknown=True).count(),
            }
        )
    return {
        "currency": "AUD",
        "categories": [_money_dict(row) for row in rows],
        "empty": not rows,
        "small_sample": sales.count() > 0 and sales.count() < 5,
    }


def build_estimate_vs_actual(filters: AnalyticsFilters) -> dict:
    sales = known_profit_sales(filtered_sales(filters)).filter(item__isnull=False)
    points = []
    estimated_fee_total = ZERO
    actual_fee_total = ZERO
    fee_count = 0
    for sale in sales.select_related("item").order_by("sale_date"):
        estimate = _estimate_from_snapshot(sale.valuation_snapshot)
        if estimate is None or estimate <= ZERO:
            continue
        actual = money(sale.sale_price)
        delta_pct = ((actual - estimate) / estimate * Decimal("100")).quantize(
            Decimal("0.01")
        )
        points.append(
            {
                "sale_id": str(sale.id),
                "item_id": str(sale.item_id),
                "sku": sale.item.sku,
                "title": sale.item.title,
                "sale_date": sale.sale_date.isoformat(),
                "estimated": estimate,
                "actual": actual,
                "delta_pct": delta_pct,
            }
        )
        estimated_fee = _estimated_fee_from_snapshot(sale.estimated_fee_snapshot)
        if estimated_fee is not None:
            estimated_fee_total += estimated_fee
            actual_fee_total += money(sale.actual_fees_total)
            fee_count += 1

    abs_errors = [abs(row["delta_pct"]) for row in points]
    within_20 = [row for row in points if abs(row["delta_pct"]) <= Decimal("20")]
    accuracy_pct = _percent(Decimal(len(within_20)), Decimal(len(points)))
    median_abs_error = median(abs_errors) if abs_errors else None
    return {
        "currency": "AUD",
        "points": [_money_dict(row) for row in points],
        "accuracy": {
            "sample_size": len(points),
            "within_20_pct": str(accuracy_pct),
            "median_abs_pct_error": str(median_abs_error) if median_abs_error is not None else None,
            "small_sample": 0 < len(points) < 5,
            "empty": len(points) == 0,
        },
        "fees": {
            "sample_size": fee_count,
            "estimated_fees_total": str(money(estimated_fee_total)),
            "actual_fees_total": str(money(actual_fee_total)),
            "delta": str(money(actual_fee_total - estimated_fee_total)),
        },
    }


def build_aging(filters: AnalyticsFilters) -> dict:
    buckets = {
        key: {
            "id": key,
            "label": label,
            "count": 0,
            "quantity_remaining": 0,
            "cost_basis": ZERO,
            "estimated_value": ZERO,
        }
        for key, label, _, _ in AGE_BUCKETS
    }
    today = timezone.localdate()
    for item in inventory_queryset(filters).select_related("acquisition"):
        remaining = item.quantity_remaining
        if remaining <= 0:
            continue
        age_days = (today - item_age_start(item)).days
        bucket = buckets[_bucket_for_age(age_days)]
        bucket["count"] += 1
        bucket["quantity_remaining"] += remaining
        bucket["cost_basis"] += item_remaining_cost(item)
        bucket["estimated_value"] += item_remaining_value(item)
    rows = [_money_dict(row) for row in buckets.values()]
    return {
        "currency": "AUD",
        "buckets": rows,
        "empty": all(row["count"] == 0 for row in rows),
    }


def build_listing_opportunities(filters: AnalyticsFilters) -> dict:
    blocked_statuses = {
        InventoryItem.Status.LISTED,
        InventoryItem.Status.SOLD,
        InventoryItem.Status.ARCHIVED,
    }
    active_draft_statuses = [
        ListingDraft.Status.DRAFT,
        ListingDraft.Status.READY,
        ListingDraft.Status.EXPORTED,
        ListingDraft.Status.STAGED,
        ListingDraft.Status.PUBLISHED,
    ]
    queryset = (
        inventory_queryset(filters)
        .exclude(status__in=blocked_statuses)
        .exclude(listing_drafts__status__in=active_draft_statuses)
        .select_related("category")
        .prefetch_related("valuation_reports")
        .distinct()
    )
    items = []
    for item in queryset:
        remaining = item.quantity_remaining
        if remaining <= 0:
            continue
        estimated = current_item_value(item)
        if estimated <= ZERO:
            continue
        cost = item_remaining_cost(item)
        estimated_margin = estimated - cost if cost > ZERO else None
        items.append(
            {
                "item_id": str(item.id),
                "sku": item.sku,
                "title": item.title,
                "category": item.category.name if item.category_id else "Uncategorised",
                "quantity_remaining": remaining,
                "estimated_value": estimated,
                "cost_basis": cost,
                "estimated_margin": estimated_margin,
                "status": item.status,
            }
        )
    items.sort(key=lambda row: (row["estimated_margin"] or row["estimated_value"]), reverse=True)
    return {
        "currency": "AUD",
        "items": [_money_dict(row) for row in items[:10]],
        "empty": len(items) == 0,
    }


def filtered_sales(filters: AnalyticsFilters):
    queryset = SaleRecord.objects.active().select_related("item", "item__category", "item__acquisition")
    if filters.start:
        queryset = queryset.filter(sale_date__gte=filters.start)
    if filters.end:
        queryset = queryset.filter(sale_date__lte=filters.end)
    if filters.category_ids:
        queryset = queryset.filter(item__category_id__in=filters.category_ids)
    if filters.channel == "external":
        queryset = queryset.filter(is_external=True)
    elif filters.channel != "all":
        queryset = queryset.filter(channel=filters.channel)
    if filters.unknown_mode == "hide":
        queryset = queryset.exclude(Q(cost_basis_unknown=True) | Q(is_external=True))
    return queryset


def known_profit_sales(queryset):
    return queryset.filter(cost_basis_unknown=False)


def inventory_queryset(filters: AnalyticsFilters):
    queryset = InventoryItem.objects.select_related("category", "acquisition")
    if filters.category_ids:
        queryset = queryset.filter(category_id__in=filters.category_ids)
    return queryset


def serialize_filters(filters: AnalyticsFilters) -> dict:
    return {
        "range": filters.range_label,
        "start": filters.start.isoformat() if filters.start else None,
        "end": filters.end.isoformat() if filters.end else None,
        "category": list(filters.category_ids),
        "channel": filters.channel,
        "unknown": filters.unknown_mode,
    }


def tile_value(tile_id: str, value, *, secondary: str = "", excluded_count: int = 0) -> dict:
    definition = KPI_TILE_CATALOG[tile_id]
    return {
        "id": tile_id,
        "label": definition["label"],
        "format": definition["format"],
        "value": str(money(value)) if isinstance(value, Decimal) and definition["format"] == "currency" else str(value),
        "secondary": secondary,
        "excluded_count": excluded_count,
        "description": definition["description"],
    }


def sum_money(queryset, field: str) -> Decimal:
    return money(queryset.aggregate(total=Sum(field))["total"] or ZERO)


def sum_sale_net(queryset) -> Decimal:
    totals = queryset.aggregate(
        revenue=Sum("sale_price"),
        fees=Sum("actual_fees_total"),
        shipping=Sum("actual_shipping_cost"),
    )
    return money(
        (totals["revenue"] or ZERO)
        - (totals["fees"] or ZERO)
        - (totals["shipping"] or ZERO)
    )


def sum_sale_profit(queryset) -> Decimal:
    total = ZERO
    for sale in queryset.select_related("item"):
        profit = sale.realised_profit
        if profit is not None:
            total += profit
    return money(total)


def average_time_to_sale(queryset) -> int:
    durations = []
    for sale in queryset.select_related("item__acquisition"):
        if not sale.item_id or not sale.item:
            continue
        start = item_age_start(sale.item)
        duration = (sale.sale_date - start).days
        if duration >= 0:
            durations.append(duration)
    if not durations:
        return 0
    return round(sum(durations) / len(durations))


def inventory_remaining_units(filters: AnalyticsFilters, *, category=None) -> int:
    queryset = inventory_queryset(filters)
    if category is not None:
        queryset = queryset.filter(category=category)
    return sum(max(item.quantity_remaining, 0) for item in queryset)


def available_inventory_cost(filters: AnalyticsFilters) -> Decimal:
    total = ZERO
    for item in inventory_queryset(filters):
        total += item_remaining_cost(item)
    return money(total)


def available_inventory_value(filters: AnalyticsFilters) -> Decimal:
    total = ZERO
    for item in inventory_queryset(filters):
        total += item_remaining_value(item)
    return money(total)


def aged_inventory_count(filters: AnalyticsFilters) -> int:
    today = timezone.localdate()
    return sum(
        1
        for item in inventory_queryset(filters).select_related("acquisition")
        if item.quantity_remaining > 0 and (today - item_age_start(item)).days > 90
    )


def item_age_start(item: InventoryItem) -> date:
    if item.acquisition_id and item.acquisition and item.acquisition.acquired_on:
        return item.acquisition.acquired_on
    return item.created_at.date()


def item_remaining_cost(item: InventoryItem) -> Decimal:
    if item.quantity_remaining <= 0 or not item.acquisition_cost:
        return ZERO
    per_unit = Decimal(item.acquisition_cost) / Decimal(item.quantity_total)
    return money(per_unit * Decimal(item.quantity_remaining))


def current_item_value(item: InventoryItem) -> Decimal:
    current = None
    manager = getattr(item, "valuation_reports", None)
    if manager is not None:
        current = manager.filter(is_current=True).order_by("-created_at").first()
    if current is not None:
        value = (
            current.suggested_price
            or current.estimate_median
            or current.patient_price
            or current.fast_sale_price
        )
        if value is not None:
            return money(value)
    return money(item.estimated_value or ZERO)


def item_remaining_value(item: InventoryItem) -> Decimal:
    if item.quantity_remaining <= 0:
        return ZERO
    value = current_item_value(item)
    if value == ZERO:
        return ZERO
    per_unit = value / Decimal(item.quantity_total)
    return money(per_unit * Decimal(item.quantity_remaining))


def _month_start(day: date, months_back: int) -> date:
    month_index = day.month - months_back
    year = day.year
    while month_index <= 0:
        month_index += 12
        year -= 1
    return date(year, month_index, 1)


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _list_param(params, key: str) -> list[str]:
    values = []
    if hasattr(params, "getlist"):
        values.extend(params.getlist(key))
    raw = params.get(key)
    if raw:
        values.extend(str(raw).split(","))
    valid = []
    seen = set()
    for value in values:
        text = str(value).strip()
        if not text or text in seen:
            continue
        try:
            UUID(text)
        except ValueError:
            continue
        seen.add(text)
        valid.append(text)
    return valid


def _percent(numerator: Decimal, denominator: Decimal) -> Decimal:
    if denominator in {ZERO, Decimal("0")}:
        return Decimal("0.00")
    return (numerator / denominator * Decimal("100")).quantize(Decimal("0.01"))


def _money_dict(row: dict) -> dict:
    converted = {}
    for key, value in row.items():
        converted[key] = str(money(value)) if isinstance(value, Decimal) and key not in {"margin", "sell_through", "delta_pct"} else (
            str(value) if isinstance(value, Decimal) else value
        )
    return converted


def _unknown_secondary(count: int) -> str:
    if count == 0:
        return ""
    plural = "sale" if count == 1 else "sales"
    return f"+{count} unknown-cost {plural} excluded."


def _estimate_from_snapshot(snapshot: dict) -> Decimal | None:
    current = (snapshot or {}).get("current_report") or {}
    for key in ["suggested_price", "estimate_median", "patient_price", "fast_sale_price"]:
        value = current.get(key)
        parsed = _to_decimal(value)
        if parsed is not None:
            return parsed
    return _to_decimal((snapshot or {}).get("item_estimated_value"))


def _estimated_fee_from_snapshot(snapshot: dict) -> Decimal | None:
    return _to_decimal((snapshot or {}).get("estimated_fees_total"))


def _to_decimal(value) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return money(value)
    except (InvalidOperation, TypeError, ValueError):
        return None


def _bucket_for_age(age_days: int) -> str:
    for key, _, start, end in AGE_BUCKETS:
        if age_days >= start and (end is None or age_days <= end):
            return key
    return "0_30"
