from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode

from apps.inventory.models import InventoryItem


EBAY_SOLD_SEARCH_BASE = "https://www.ebay.com.au/sch/i.html"


@dataclass(frozen=True)
class SoldSearchLink:
    id: str
    label: str
    query: str
    url: str


def build_sold_search_links(item: InventoryItem) -> list[SoldSearchLink]:
    links: list[SoldSearchLink] = []
    seen: set[tuple[str, str]] = set()

    def add(link_id: str, label: str, query: str, extra: dict[str, str] | None = None) -> None:
        cleaned = " ".join(str(query).split())
        if not cleaned:
            return
        key = (link_id, cleaned.lower())
        if key in seen:
            return
        seen.add(key)
        params = {
            "_nkw": cleaned,
            "LH_Sold": "1",
            "LH_Complete": "1",
            "_sop": "13",
            **(extra or {}),
        }
        links.append(
            SoldSearchLink(
                id=link_id,
                label=label,
                query=cleaned,
                url=f"{EBAY_SOLD_SEARCH_BASE}?{urlencode(params)}",
            )
        )

    broad = broad_query(item)
    add("broad", "Broad sold search", broad)
    add("exact", "Exact title sold search", item.title or broad)

    condition_query = condition_or_grade_query(item)
    if condition_query:
        add("condition", "Grade or condition angle", condition_query)

    add("auction", "Auction sold search", broad, {"LH_Auction": "1"})
    add("fixed_price", "Fixed-price sold search", broad, {"LH_BIN": "1"})

    price = price_anchor(item)
    if price is not None and price > 0:
        low = max(Decimal("0.01"), (price * Decimal("0.70")).quantize(Decimal("0.01")))
        high = (price * Decimal("1.30")).quantize(Decimal("0.01"))
        add(
            "price_bounded",
            "Price-bounded sold search",
            broad,
            {"_udlo": str(low), "_udhi": str(high)},
        )

    if item.category_id and item.category and item.category.name:
        category_query = f"{broad} {item.category.name}"
        add("category", "Category-narrowed sold search", category_query)

    return links


def broad_query(item: InventoryItem) -> str:
    attributes = item.attributes or {}
    profile = item.category.profile_key if item.category_id and item.category else ""
    tokens: list[str] = []

    if profile in {"stamps", "coins"}:
        for key in ["country", "year", "denomination", "variety", "mint_mark", "ruler_or_reign"]:
            value = attributes.get(key)
            if value:
                tokens.append(str(value))
    elif profile == "banknotes":
        for key in ["country", "denomination", "series_year", "prefix_serial", "signature_variety"]:
            value = attributes.get(key)
            if value:
                tokens.append(str(value))
    elif profile == "phones":
        for key in ["brand", "model", "storage_gb"]:
            value = attributes.get(key)
            if value:
                tokens.append(f"{value}GB" if key == "storage_gb" else str(value))
    elif profile == "gold":
        for key in ["metal", "form", "weight_g", "karat"]:
            value = attributes.get(key)
            if value:
                tokens.append(f"{value}ct" if key == "karat" else str(value))

    if not tokens and item.title:
        tokens = item.title.split()[:8]
    return " ".join(tokens)


def condition_or_grade_query(item: InventoryItem) -> str:
    attributes = item.attributes or {}
    parts = [broad_query(item)]
    grade = attributes.get("grade")
    if grade:
        parts.append(str(grade))
    elif item.condition and item.condition != InventoryItem.Condition.UNGRADED:
        parts.append(item.get_condition_display())
    return " ".join(part for part in parts if part)


def price_anchor(item: InventoryItem) -> Decimal | None:
    manager = getattr(item, "valuation_reports", None)
    if manager is not None:
        current = manager.filter(is_current=True).order_by("-created_at").first()
        if current is not None:
            for value in [
                current.suggested_price,
                current.estimate_median,
                current.patient_price,
                current.fast_sale_price,
                item.estimated_value,
            ]:
                parsed = _decimal_or_none(value)
                if parsed is not None and parsed > 0:
                    return parsed
    return _decimal_or_none(item.estimated_value)


def _decimal_or_none(value) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
