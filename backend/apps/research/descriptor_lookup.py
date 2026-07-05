from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from statistics import median
from typing import Any, Iterable

from django.db.models import Q
from django.utils import timezone

from apps.catalog.models import ProductCategory
from apps.inventory.models import InventoryItem
from apps.profit.services import EvidenceSource, PriceBasis, normalize_to_seller_receives
from apps.research.models import Comparable
from apps.sales.models import SaleRecord


CENT = Decimal("0.01")
TOKEN_STOPWORDS = {
    "and",
    "the",
    "with",
    "for",
    "from",
    "item",
    "coin",
    "stamp",
    "phone",
    "gold",
}
STRENGTH_TOOLTIP = "STRONG = at least 3 known-basis rows from the last 12 months, including at least 1 from the last 90 days. Otherwise THIN."


@dataclass(frozen=True)
class DescriptorContext:
    category: ProductCategory | None
    terms: list[str]
    attributes: dict[str, Any]


@dataclass(frozen=True)
class DescriptorEvidenceRow:
    id: str
    record_type: str
    source: str
    source_label: str
    label: str
    rank: int
    match_scope: str
    match_reason: str
    price: Decimal | None
    price_basis: str
    seller_receives: Decimal | None
    basis_uncertain: bool
    basis_label: str
    currency: str
    date: date | None
    url: str
    item_id: str | None
    item_sku: str
    own_sale: bool


def descriptor_lookup_payload(*, category_id: str | None, terms: Iterable[str] | str, attributes: dict | None = None) -> dict:
    context = descriptor_context(category_id=category_id, terms=terms, attributes=attributes or {})
    rows = descriptor_lookup_rows(context)
    known = [row for row in rows if row.seller_receives is not None and not row.basis_uncertain]
    unknown = [row for row in rows if row.basis_uncertain]
    return {
        "lookup": {
            "category": str(context.category.id) if context.category else None,
            "category_label": context.category.name if context.category else "",
            "terms": context.terms,
            "attributes": context.attributes,
            "transient": True,
        },
        "rows": [serialize_lookup_row(row) for row in rows],
        "stats": stats_payload(known, unknown),
        "strength": strength_payload(known),
        "empty": not rows,
        "empty_state": empty_state(rows, known),
    }


def descriptor_context(*, category_id: str | None, terms: Iterable[str] | str, attributes: dict) -> DescriptorContext:
    category = ProductCategory.objects.filter(pk=category_id).first() if category_id else None
    parsed_terms = parse_terms(terms)
    clean_attrs = {
        str(key): value
        for key, value in (attributes or {}).items()
        if not is_empty_value(value)
    }
    return DescriptorContext(category=category, terms=parsed_terms, attributes=clean_attrs)


def descriptor_lookup_rows(context: DescriptorContext) -> list[DescriptorEvidenceRow]:
    sales = (
        SaleRecord.objects.active()
        .select_related("item", "item__category", "listing_draft")
        .exclude(item__isnull=True)
        .order_by("-sale_date", "-created_at")
    )
    exact_sales: list[DescriptorEvidenceRow] = []
    similar_sales: list[DescriptorEvidenceRow] = []
    for sale in sales[:250]:
        reasons = sale_match_reasons(context, sale.item)
        if not reasons:
            continue
        exact = is_exact_match(context, sale.item, reasons)
        row = sale_row(sale, rank=0 if exact else 1, scope="exact" if exact else "similar", reason="; ".join(reasons))
        if exact:
            exact_sales.append(row)
        else:
            similar_sales.append(row)

    comparable_rows = []
    for comp in comparable_queryset(context)[:250]:
        reasons = comparable_match_reasons(context, comp)
        if not reasons:
            continue
        comparable_rows.append(comparable_row(comp, reason="; ".join(reasons)))

    return sorted(exact_sales, key=row_sort_key) + sorted(similar_sales, key=row_sort_key) + sorted(comparable_rows, key=row_sort_key)


def comparable_queryset(context: DescriptorContext):
    queryset = Comparable.objects.select_related("item", "item__category", "descriptor_category").filter(kind=Comparable.Kind.SOLD)
    if context.category:
        queryset = queryset.filter(Q(descriptor_category=context.category) | Q(item__category=context.category))
    return queryset.order_by("-observed_on", "-created_at").distinct()


def sale_match_reasons(context: DescriptorContext, item: InventoryItem | None) -> list[str]:
    if item is None:
        return []
    reasons: list[str] = []
    if context.category and item.category_id == context.category.id:
        reasons.append("same category")
    token_matches = sorted(lookup_tokens(context) & item_tokens(item))
    if token_matches:
        reasons.append("matched terms: " + ", ".join(token_matches[:4]))
    for key, value in context.attributes.items():
        if attribute_matches(item.attributes or {}, key, value):
            reasons.append(f"same {key.replace('_', ' ')}")
    return reasons[:5]


def comparable_match_reasons(context: DescriptorContext, comp: Comparable) -> list[str]:
    reasons: list[str] = []
    comp_category = comp.descriptor_category or (comp.item.category if comp.item_id else None)
    if context.category and comp_category and comp_category.id == context.category.id:
        reasons.append("same category")
    token_matches = sorted(lookup_tokens(context) & comparable_tokens(comp))
    if token_matches:
        reasons.append("matched terms: " + ", ".join(token_matches[:4]))
    comp_attrs = comp.descriptor_attributes or {}
    item_attrs = comp.item.attributes if comp.item_id and comp.item else {}
    for key, value in context.attributes.items():
        if attribute_matches(comp_attrs, key, value) or attribute_matches(item_attrs, key, value):
            reasons.append(f"same {key.replace('_', ' ')}")
    if not reasons and comp.match_reason:
        simple_reason = comp.match_reason.lower()
        if context.category and "same category" in simple_reason:
            reasons.append("same category")
    return reasons[:5]


def is_exact_match(context: DescriptorContext, item: InventoryItem | None, reasons: list[str]) -> bool:
    if item is None:
        return False
    if context.category and item.category_id != context.category.id:
        return False
    required_tokens = lookup_tokens(context)
    if required_tokens and not required_tokens.issubset(item_tokens(item)):
        return False
    for key, value in context.attributes.items():
        if not attribute_matches(item.attributes or {}, key, value):
            return False
    return bool(reasons)


def sale_row(sale: SaleRecord, *, rank: int, scope: str, reason: str) -> DescriptorEvidenceRow:
    sale_item = sale.item
    price = money(Decimal(sale.sale_price) / Decimal(sale.quantity))
    normalized = normalize_to_seller_receives(price, PriceBasis.SELLER_RECEIVES)
    return DescriptorEvidenceRow(
        id=f"sale:{sale.id}",
        record_type="sale",
        source=EvidenceSource.OWN_SALE_EXACT if scope == "exact" else EvidenceSource.OWN_SALE_SIMILAR,
        source_label="Own sale",
        label=sale_item.title or sale_item.sku,
        rank=rank,
        match_scope=scope,
        match_reason=reason,
        price=price,
        price_basis=PriceBasis.SELLER_RECEIVES,
        seller_receives=normalized.seller_receives,
        basis_uncertain=normalized.basis_uncertain,
        basis_label=normalized.label,
        currency=sale_item.currency,
        date=sale.sale_date,
        url="",
        item_id=str(sale_item.id),
        item_sku=sale_item.sku,
        own_sale=True,
    )


def comparable_row(comp: Comparable, *, reason: str) -> DescriptorEvidenceRow:
    normalized = normalize_to_seller_receives(comp.price, comp.price_basis)
    return DescriptorEvidenceRow(
        id=f"comp:{comp.id}",
        record_type="comparable",
        source=EvidenceSource.APPROVED_COMP,
        source_label=comp.source or comp.get_kind_display(),
        label=comp.title or (comp.item.title if comp.item_id and comp.item else "") or (comp.item.sku if comp.item_id and comp.item else "Captured comparable"),
        rank=2,
        match_scope=comp.match_scope,
        match_reason=reason or comp.match_reason,
        price=money(comp.price) if comp.price is not None else None,
        price_basis=comp.price_basis,
        seller_receives=normalized.seller_receives,
        basis_uncertain=normalized.basis_uncertain,
        basis_label=normalized.label,
        currency=comp.currency,
        date=comp.observed_on,
        url=comp.url,
        item_id=str(comp.item_id) if comp.item_id else None,
        item_sku=comp.item.sku if comp.item_id and comp.item else "",
        own_sale=False,
    )


def stats_payload(known: list[DescriptorEvidenceRow], unknown: list[DescriptorEvidenceRow]) -> dict:
    values = sorted(row.seller_receives for row in known if row.seller_receives is not None)
    newest = newest_date(known)
    return {
        "basis": PriceBasis.SELLER_RECEIVES,
        "low": str(money(values[0])) if values else None,
        "median": str(money(median(values))) if values else None,
        "high": str(money(values[-1])) if values else None,
        "count": len(values),
        "unknown_basis_count": len(unknown),
        "newest_date": newest.isoformat() if newest else None,
        "newest_age_days": (timezone.localdate() - newest).days if newest else None,
    }


def strength_payload(known: list[DescriptorEvidenceRow]) -> dict:
    today = timezone.localdate()
    within_year = [row for row in known if row.date and (today - row.date).days <= 365]
    within_90 = [row for row in known if row.date and (today - row.date).days <= 90]
    strength = "STRONG" if len(within_year) >= 3 and len(within_90) >= 1 else "THIN"
    newest = newest_date(known)
    return {
        "label": strength,
        "known_basis_count": len(known),
        "newest_age_days": (today - newest).days if newest else None,
        "tooltip": STRENGTH_TOOLTIP,
    }


def serialize_lookup_row(row: DescriptorEvidenceRow) -> dict:
    return {
        "id": row.id,
        "record_type": row.record_type,
        "source": row.source,
        "source_label": row.source_label,
        "label": row.label,
        "rank": row.rank,
        "match_scope": row.match_scope,
        "match_reason": row.match_reason,
        "price": str(row.price) if row.price is not None else None,
        "price_basis": row.price_basis,
        "seller_receives": str(row.seller_receives) if row.seller_receives is not None else None,
        "basis_uncertain": row.basis_uncertain,
        "basis_label": row.basis_label,
        "currency": row.currency,
        "date": row.date.isoformat() if row.date else None,
        "url": row.url,
        "item": row.item_id,
        "item_sku": row.item_sku,
        "own_sale": row.own_sale,
    }


def parse_terms(terms: Iterable[str] | str) -> list[str]:
    if isinstance(terms, str):
        raw_terms = terms.replace(",", " ").split()
    else:
        raw_terms = []
        for term in terms:
            raw_terms.extend(str(term).replace(",", " ").split())
    return sorted({token for token in normalize_tokens(" ".join(raw_terms))})


def lookup_tokens(context: DescriptorContext) -> set[str]:
    tokens = set(context.terms)
    for value in context.attributes.values():
        tokens.update(normalize_tokens(str(value)))
    return tokens


def item_tokens(item: InventoryItem) -> set[str]:
    text = " ".join(
        [
            item.title or "",
            item.sku or "",
            item.category.name if item.category else "",
            " ".join(str(value) for value in (item.attributes or {}).values()),
        ]
    )
    return normalize_tokens(text)


def comparable_tokens(comp: Comparable) -> set[str]:
    text = " ".join(
        [
            comp.title or "",
            comp.source or "",
            comp.source_tag or "",
            comp.match_reason or "",
            " ".join(str(term) for term in (comp.descriptor_terms or [])),
            " ".join(str(value) for value in (comp.descriptor_attributes or {}).values()),
            comp.item.title if comp.item_id and comp.item else "",
            " ".join(str(value) for value in ((comp.item.attributes if comp.item_id and comp.item else {}) or {}).values()),
        ]
    )
    return normalize_tokens(text)


def normalize_tokens(text: str) -> set[str]:
    return {
        token.lower()
        for token in "".join(char.lower() if char.isalnum() else " " for char in text).split()
        if len(token) >= 2 and token.lower() not in TOKEN_STOPWORDS
    }


def attribute_matches(attributes: dict, key: str, expected: Any) -> bool:
    value = attributes.get(key)
    if is_empty_value(value):
        return False
    return str(value).strip().lower() == str(expected).strip().lower()


def is_empty_value(value: Any) -> bool:
    return value is None or value == "" or value == []


def row_sort_key(row: DescriptorEvidenceRow):
    date_key = row.date or date.min
    return (row.rank, -date_key.toordinal(), row.label.lower())


def newest_date(rows: list[DescriptorEvidenceRow]) -> date | None:
    dated = [row.date for row in rows if row.date]
    return max(dated) if dated else None


def empty_state(rows: list[DescriptorEvidenceRow], known: list[DescriptorEvidenceRow]) -> dict:
    if rows and not known:
        return {
            "title": "Evidence basis needs review",
            "detail": "Matching rows are visible, but their price basis is uncertain. Pick a known-basis row or capture one before using precise stats.",
        }
    if rows:
        return {
            "title": "Thin descriptor evidence",
            "detail": "Use the known-basis rows as evidence, not a valuation. Capture more verified comps to strengthen the range.",
        }
    return {
        "title": "No matching evidence yet",
        "detail": "Capture a verified sold comp from this lookup, or use a clearly labelled what-if sell price.",
    }


def money(value) -> Decimal:
    return Decimal(str(value or "0")).quantize(CENT, rounding=ROUND_HALF_UP)
