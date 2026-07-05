from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from string import Formatter

from django.utils import timezone

from apps.inventory.models import InventoryItem
from apps.listing.models import ListingDraft


CENT = Decimal("0.01")
TEMPLATE_PATH = Path(__file__).with_name("copy_pack_templates.json")
DEFAULT_CHANNEL = "generic"
COPY_PACK_CHANNELS = {"ebay", "facebook_marketplace", "gumtree", "generic"}
CLAIMS_REQUIRE_FIELD_SUPPORT = {"mint", "rare", "perfect", "tested"}


@dataclass(frozen=True)
class PriceSource:
    value: Decimal | None
    label: str
    hint: str
    basis: str


def render_copy_pack(
    item: InventoryItem,
    *,
    channel: str = DEFAULT_CHANNEL,
    evidence_price: str | Decimal | None = None,
    evidence_label: str = "",
) -> dict:
    registry = load_template_registry()
    channel_key = channel if channel in registry else DEFAULT_CHANNEL
    template = registry[channel_key]
    context = copy_context(item, evidence_price=evidence_price, evidence_label=evidence_label)
    sections = {}
    for key, pattern in template["sections"].items():
        sections[key] = _render_template(pattern, context)
    whole_ad = "\n\n".join(
        value for value in [
            sections["title"],
            sections["description"],
            sections["price_line"],
            sections["postage_pickup_line"],
        ]
        if value
    )
    return {
        "item": str(item.id),
        "channel": channel_key,
        "channel_label": template["label"],
        "sections": sections,
        "whole_ad": whole_ad,
        "price_source": {
            "basis": context["price_basis"],
            "label": context["price_source_label"],
            "hint": context["price_hint"],
        },
        "rendered_at": timezone.now().isoformat(),
    }


def load_template_registry() -> dict:
    with TEMPLATE_PATH.open("r", encoding="utf-8") as handle:
        registry = json.load(handle)
    for channel, template in registry.items():
        if channel not in COPY_PACK_CHANNELS:
            raise ValueError(f"Unsupported copy-pack channel: {channel}")
        sections = template.get("sections") or {}
        required = {"title", "description", "price_line", "postage_pickup_line"}
        missing = required - set(sections)
        if missing:
            raise ValueError(f"{channel} template missing section(s): {', '.join(sorted(missing))}")
    return registry


def copy_context(
    item: InventoryItem,
    *,
    evidence_price: str | Decimal | None = None,
    evidence_label: str = "",
) -> dict:
    price_source = choose_price(item, evidence_price=evidence_price, evidence_label=evidence_label)
    return {
        "title": item.title.strip() or "[title not set]",
        "category": item.category.name if item.category_id and item.category else "[category not set]",
        "condition": item.get_condition_display() if item.condition else "[condition not set]",
        "attributes": attributes_text(item),
        "price": format_price(price_source.value) if price_source.value is not None else "[price not set - choose an item asking price or human-picked evidence]",
        "price_basis": price_source.basis,
        "price_source_label": price_source.label,
        "price_hint": price_source.hint,
        "postage": postage_text(item),
    }


def choose_price(
    item: InventoryItem,
    *,
    evidence_price: str | Decimal | None = None,
    evidence_label: str = "",
) -> PriceSource:
    parsed_evidence = parse_money(evidence_price)
    if parsed_evidence is not None:
        return PriceSource(
            value=parsed_evidence,
            label=evidence_label.strip() or "human-picked evidence",
            hint="Price copied from a human-picked evidence figure.",
            basis="human_picked_evidence",
        )
    listed_price = latest_listing_price(item)
    if listed_price is not None:
        return PriceSource(
            value=listed_price,
            label="item listed price",
            hint="Price copied from an existing Magpie listing draft.",
            basis="item_asking_or_listed_price",
        )
    if item.target_price is not None:
        return PriceSource(
            value=money(item.target_price),
            label="item asking price",
            hint="Price copied from the item's own asking price.",
            basis="item_asking_or_listed_price",
        )
    return PriceSource(
        value=None,
        label="missing",
        hint="Set an asking/listed price or pick an evidence figure before copying a price line.",
        basis="missing",
    )


def latest_listing_price(item: InventoryItem) -> Decimal | None:
    draft = (
        ListingDraft.objects.filter(item=item, price__isnull=False)
        .order_by("-updated_at", "-created_at")
        .first()
    )
    return money(draft.price) if draft and draft.price is not None else None


def attributes_text(item: InventoryItem) -> str:
    attributes = item.attributes or {}
    if not attributes:
        return "[details not set]"
    pairs = []
    for key in sorted(attributes):
        value = attributes[key]
        if value is None or value == "" or value == []:
            continue
        label = str(key).replace("_", " ").strip()
        if isinstance(value, (dict, list)):
            rendered_value = json.dumps(value, sort_keys=True)
        else:
            rendered_value = str(value)
        pairs.append(f"{label}: {rendered_value}")
    return "; ".join(pairs) if pairs else "[details not set]"


def postage_text(item: InventoryItem) -> str:
    parts = []
    if item.est_outbound_shipping is not None:
        parts.append(f"Postage estimate {format_price(item.est_outbound_shipping)}")
    if item.est_packaging_cost is not None:
        parts.append(f"Packaging estimate {format_price(item.est_packaging_cost)}")
    return "; ".join(parts) if parts else "[postage or pickup not set]"


def _render_template(pattern: str, context: dict) -> str:
    rendered = pattern
    for _, field, _, _ in Formatter().parse(pattern):
        if not field:
            continue
        rendered = rendered.replace("{" + field + "}", str(context.get(field, f"[{field} not set]")))
    return rendered


def parse_money(value) -> Decimal | None:
    if value in {None, ""}:
        return None
    try:
        return money(value)
    except (InvalidOperation, ValueError, TypeError):
        return None


def money(value) -> Decimal:
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


def format_price(value) -> str:
    return f"A${money(value):,.2f}"
