from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable

from django.utils import timezone

from apps.inventory.models import InventoryItem
from apps.research.models import Comparable
from apps.research.pricing_sources import pricing_source_links
from apps.sales.models import SaleRecord
from apps.profit.services import PriceBasis, normalize_to_seller_receives


CENT = Decimal("0.01")


@dataclass(frozen=True)
class PricingEvidenceRow:
    id: str
    record_type: str
    own_sale: bool
    match_scope: str
    match_reason: str
    date: str | None
    title: str
    sku: str
    source_tag: str
    source_label: str
    condition: str
    grade: str
    sale_format: str
    price: Decimal | None
    price_basis: str
    canonical_price: Decimal | None
    basis_uncertain: bool
    basis_label: str
    currency: str
    quantity: int
    url: str
    notes: str


def pricing_evidence_payload(item: InventoryItem) -> dict:
    rows = evidence_rows(item)
    priced_rows = [row for row in rows if row.price is not None]
    precise_rows = [row for row in priced_rows if row.canonical_price is not None and not row.basis_uncertain]
    own_rows = [row for row in rows if row.own_sale]
    comparable_rows = [row for row in rows if row.record_type == "comparable"]

    return {
        "item": str(item.id),
        "currency": item.currency,
        "source_links": [link.__dict__ for link in pricing_source_links(item)],
        "headline": [serialize_row(row) for row in rows[:12]],
        "own_sales": [serialize_row(row) for row in own_rows],
        "comparables": [serialize_row(row) for row in comparable_rows],
        "grids": {
            "condition_grade": grid_for(priced_rows, condition_grade_key),
            "sale_format": grid_for(priced_rows, lambda row: row.sale_format or "unknown"),
            "recency": grid_for(priced_rows, recency_key),
            "source": grid_for(priced_rows, lambda row: row.source_tag or "uncategorised"),
        },
        "summary": {
            "evidence_count": len(rows),
            "priced_count": len(priced_rows),
            "precise_priced_count": len(precise_rows),
            "basis_uncertain_count": sum(1 for row in priced_rows if row.basis_uncertain),
            "own_sale_count": len(own_rows),
            "comparable_count": len(comparable_rows),
            "exact_count": sum(1 for row in rows if row.match_scope == "exact"),
            "similar_count": sum(1 for row in rows if row.match_scope == "similar"),
            "thin": len(priced_rows) < 3,
            "empty": len(priced_rows) == 0,
        },
        "empty_state": empty_state(len(priced_rows)),
    }


def evidence_rows(item: InventoryItem) -> list[PricingEvidenceRow]:
    exact_sales = [sale_row(sale, "exact", "same inventory item") for sale in exact_sale_queryset(item)]
    similar_sales = [
        sale_row(sale, "similar", "; ".join(reasons))
        for sale, reasons in similar_sale_matches(item)
    ]
    comparable_rows = [comparable_row(comp) for comp in comparable_queryset(item)]
    return exact_sales + similar_sales + comparable_rows


def exact_sale_queryset(item: InventoryItem):
    return (
        SaleRecord.objects.active()
        .select_related("item", "item__category", "listing_draft")
        .filter(item=item)
        .order_by("-sale_date", "-created_at")
    )


def similar_sale_matches(item: InventoryItem) -> list[tuple[SaleRecord, list[str]]]:
    queryset = (
        SaleRecord.objects.active()
        .select_related("item", "item__category", "listing_draft")
        .exclude(item__isnull=True)
        .exclude(item=item)
        .order_by("-sale_date", "-created_at")
    )
    matches: list[tuple[SaleRecord, list[str]]] = []
    for sale in queryset[:100]:
        reasons = simple_match_reasons(item, sale.item)
        if reasons:
            matches.append((sale, reasons))
    return matches[:12]


def comparable_queryset(item: InventoryItem):
    return item.comparables.order_by("-observed_on", "-created_at")


def sale_row(sale: SaleRecord, scope: str, reason: str) -> PricingEvidenceRow:
    sale_item = sale.item
    price = money(Decimal(sale.sale_price) / Decimal(sale.quantity))
    normalized = normalize_to_seller_receives(price, PriceBasis.SELLER_RECEIVES)
    grade = ""
    if sale_item and sale_item.attributes:
        grade = str(sale_item.attributes.get("grade") or "")
    return PricingEvidenceRow(
        id=f"sale:{sale.id}",
        record_type="sale",
        own_sale=True,
        match_scope=scope,
        match_reason=reason,
        date=sale.sale_date.isoformat(),
        title=sale_item.title if sale_item else "External sale",
        sku=sale_item.sku if sale_item else "",
        source_tag="own_sale",
        source_label="Own sale",
        condition=sale_item.condition if sale_item else "",
        grade=grade,
        sale_format=sale_format_for_sale(sale),
        price=price,
        price_basis=PriceBasis.SELLER_RECEIVES,
        canonical_price=normalized.seller_receives,
        basis_uncertain=normalized.basis_uncertain,
        basis_label=normalized.label,
        currency=sale_item.currency if sale_item else "AUD",
        quantity=sale.quantity,
        url="",
        notes=sale.notes,
    )


def comparable_row(comp: Comparable) -> PricingEvidenceRow:
    normalized = normalize_to_seller_receives(comp.price, comp.price_basis)
    return PricingEvidenceRow(
        id=f"comp:{comp.id}",
        record_type="comparable",
        own_sale=False,
        match_scope=comp.match_scope,
        match_reason=comp.match_reason or default_comparable_reason(comp),
        date=comp.observed_on.isoformat() if comp.observed_on else None,
        title=comp.title,
        sku=comp.item.sku,
        source_tag=comp.source_tag or source_tag_from_text(comp.source or comp.kind),
        source_label=comp.source or comp.get_kind_display(),
        condition=comp.condition,
        grade=comp.grade,
        sale_format=comp.sale_format,
        price=money(comp.price) if comp.price is not None else None,
        price_basis=comp.price_basis,
        canonical_price=normalized.seller_receives,
        basis_uncertain=normalized.basis_uncertain,
        basis_label=normalized.label,
        currency=comp.currency,
        quantity=1,
        url=comp.url,
        notes=comp.notes,
    )


def simple_match_reasons(target: InventoryItem, candidate: InventoryItem) -> list[str]:
    reasons: list[str] = []
    if target.category_id and target.category_id == candidate.category_id:
        reasons.append("same category")
    target_attributes = target.attributes or {}
    candidate_attributes = candidate.attributes or {}
    for key in ["country", "denomination", "year", "brand", "model", "metal", "karat", "form"]:
        if target_attributes.get(key) and target_attributes.get(key) == candidate_attributes.get(key):
            reasons.append(f"same {key.replace('_', ' ')}")
    shared = sorted(title_tokens(target.title) & title_tokens(candidate.title))
    if shared:
        reasons.append(f"shared title token: {shared[0]}")
    return reasons[:4]


def title_tokens(title: str) -> set[str]:
    stop = {"the", "and", "with", "for", "coin", "stamp", "phone", "gold"}
    return {
        token.lower()
        for token in "".join(char if char.isalnum() else " " for char in title).split()
        if len(token) >= 4 and token.lower() not in stop
    }


def sale_format_for_sale(sale: SaleRecord) -> str:
    if sale.listing_draft_id and sale.listing_draft:
        if sale.listing_draft.listing_format == "auction":
            return Comparable.SaleFormat.AUCTION
        if sale.listing_draft.listing_format == "fixed":
            return Comparable.SaleFormat.FIXED_PRICE
    if sale.channel == SaleRecord.Channel.EBAY_AU:
        return Comparable.SaleFormat.UNKNOWN
    return Comparable.SaleFormat.OTHER


def default_comparable_reason(comp: Comparable) -> str:
    if comp.match_scope == Comparable.MatchScope.EXACT:
        return "user-captured exact comparable"
    return "user-captured similar comparable"


def grid_for(rows: Iterable[PricingEvidenceRow], key_func) -> list[dict]:
    buckets: dict[str, list[PricingEvidenceRow]] = {}
    for row in rows:
        key = key_func(row) or "unknown"
        buckets.setdefault(key, []).append(row)
    cells = []
    for key, bucket_rows in sorted(buckets.items(), key=lambda item: item[0]):
        prices = sorted(
            row.canonical_price
            for row in bucket_rows
            if row.canonical_price is not None and not row.basis_uncertain
        )
        cells.append(
            {
                "key": key,
                "label": label_for_key(key),
                "low": str(money(prices[0])) if prices else None,
                "median": str(median(prices)) if prices else None,
                "high": str(money(prices[-1])) if prices else None,
                "count": len(prices),
                "basis_uncertain_count": sum(1 for row in bucket_rows if row.basis_uncertain),
                "own_sale_count": sum(1 for row in bucket_rows if row.own_sale),
                "thin": len(prices) < 3,
            }
        )
    return cells


def condition_grade_key(row: PricingEvidenceRow) -> str:
    grade = row.grade.strip()
    condition = row.condition.strip()
    if grade and condition:
        return f"{condition} / {grade}"
    return grade or condition or "unknown"


def recency_key(row: PricingEvidenceRow) -> str:
    if not row.date:
        return "undated"
    today = timezone.localdate()
    age = (today - date.fromisoformat(row.date)).days
    if age <= 90:
        return "0-90 days"
    if age <= 365:
        return "91-365 days"
    return "older than 365 days"


def serialize_row(row: PricingEvidenceRow) -> dict:
    return {
        "id": row.id,
        "record_type": row.record_type,
        "own_sale": row.own_sale,
        "match_scope": row.match_scope,
        "match_reason": row.match_reason,
        "date": row.date,
        "title": row.title,
        "sku": row.sku,
        "source_tag": row.source_tag,
        "source_label": row.source_label,
        "condition": row.condition,
        "grade": row.grade,
        "sale_format": row.sale_format,
        "price": str(row.price) if row.price is not None else None,
        "price_basis": row.price_basis,
        "canonical_price": str(row.canonical_price) if row.canonical_price is not None else None,
        "basis_uncertain": row.basis_uncertain,
        "basis_label": row.basis_label,
        "currency": row.currency,
        "quantity": row.quantity,
        "url": row.url,
        "notes": row.notes,
    }


def median(prices: list[Decimal]) -> Decimal:
    middle = len(prices) // 2
    if len(prices) % 2:
        return money(prices[middle])
    return money((prices[middle - 1] + prices[middle]) / Decimal("2"))


def money(value) -> Decimal:
    return Decimal(str(value or "0")).quantize(CENT, rounding=ROUND_HALF_UP)


def source_tag_from_text(value: str) -> str:
    text = "".join(char.lower() if char.isalnum() else "_" for char in value).strip("_")
    while "__" in text:
        text = text.replace("__", "_")
    return text[:80] or "manual"


def label_for_key(key: str) -> str:
    return key.replace("_", " ").title()


def empty_state(priced_count: int) -> dict:
    if priced_count:
        return {
            "title": "Thin pricing evidence",
            "detail": "Treat this as a ledger of evidence, not a price estimate. Add more captured comps as you verify sources.",
        }
    return {
        "title": "No pricing evidence yet",
        "detail": "Open a source link, record a verified sold result, or sell this item and the pricing grid will fill from real evidence.",
    }
