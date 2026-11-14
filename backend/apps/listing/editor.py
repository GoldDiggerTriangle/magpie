"""Local listing editing. Metadata refresh is explicit; saving never stages."""

from copy import copy, deepcopy
from decimal import Decimal, InvalidOperation
from html import escape
import hashlib
import json

from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.listing.context import safe_context
from apps.listing.copy_packs import render_copy_pack
from apps.listing.editor_metadata import editor_metadata, mapping, text
from apps.listing.readiness import check_readiness


EDITABLE_CHANNEL_FIELDS = {
    "category_id", "category_name", "category_tree_id", "condition_id", "listing_duration",
    "payment_policy_id", "fulfillment_policy_id", "return_policy_id", "merchant_location_key",
}
LISTING_FIELDS = (
    "title", "subtitle", "description_html", "listing_format", "price", "currency", "quantity",
    "item_specifics", "photo_ids", "include_sku_footer", "boilerplate_id", "est_shipping_note",
)


def description_default(item):
    # Reuse the copy-pack registry, but keep private inventory fields out of ads.
    public_item = copy(item)
    context = safe_context(item)
    public_item.attributes = {key: value for key, value in (item.attributes or {}).items() if key in context}
    body = render_copy_pack(public_item, channel="ebay")["sections"]["description"]
    return "".join(f"<p>{escape(line)}</p>" for line in body.splitlines() if line)


def price_options(draft):
    from apps.research.pricing_evidence import evidence_rows

    options = []
    if draft.item.target_price is not None and draft.item.target_price > 0 and draft.currency == draft.item.currency:
        options.append({"id": "item_asking", "value": str(draft.item.target_price), "label": "Item asking price (human-set)"})
    for row in evidence_rows(draft.item):
        if row.canonical_price is None or row.canonical_price <= 0 or row.basis_uncertain or row.currency != draft.currency:
            continue
        options.append({"id": row.id, "value": str(row.canonical_price),
                        "label": f"{row.source_label}: {row.title} ({row.date or 'date unknown'}; {row.match_reason})"})
    return options


def apply_price_choice(draft, data, choice):
    meta = deepcopy(mapping(draft.generated_meta))
    changed = "price" in data and data["price"] != draft.price
    currency_changed = "currency" in data and data["currency"] != draft.currency
    if data.get("price", draft.price) is None:
        meta.pop("price_source", None)
        return meta
    if choice is None:
        if changed or currency_changed:
            raise ValidationError({"price_choice": "Confirm a human asking price or explicitly pick owned evidence (D-129)."})
        return meta
    kind = text(mapping(choice).get("kind"))
    label = "Human asking price"
    if kind == "human_asking":
        value = data.get("price", draft.price)
    elif kind == "owned_evidence":
        candidate = copy(draft)
        candidate.currency = data.get("currency", draft.currency)
        option = next((row for row in price_options(candidate) if row["id"] == text(choice.get("id"))), None)
        if option is None:
            raise ValidationError({"price_choice": "Choose known-basis evidence belonging to this item, in the listing currency."})
        value, label = Decimal(option["value"]), option["label"]
        data["price"] = value
    else:
        raise ValidationError({"price_choice": "Prices cannot come from AI, valuations or an unconfirmed source."})
    try:
        if not Decimal(value).is_finite() or Decimal(value) <= 0:
            raise ValueError
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError({"price": "Confirm a positive asking price."}) from None
    meta["price_source"] = {"kind": kind, "id": text(choice.get("id")) if kind == "owned_evidence" else "",
                            "label": label, "value": str(value), "currency": data.get("currency", draft.currency),
                            "price_basis": "seller_receives", "captured_at": timezone.now().isoformat()}
    return meta


def signature(draft):
    values = {name: getattr(draft, name) for name in LISTING_FIELDS}
    values["channel"] = {key: mapping(draft.channel_data).get(key) for key in sorted(EDITABLE_CHANNEL_FIELDS)}
    return hashlib.sha256(json.dumps(values, sort_keys=True, default=str).encode()).hexdigest()


def snapshot_signature(draft):
    return hashlib.sha256(json.dumps(mapping(draft.channel_data).get("last_payload_snapshot"), sort_keys=True, default=str).encode()).hexdigest()


def staged_changes(draft):
    data = mapping(draft.channel_data)
    if not data.get("offer_id"):
        return False
    baseline = mapping(data.get("editor_staged_baseline"))
    if baseline and baseline.get("snapshot") == snapshot_signature(draft) and baseline.get("fields") != signature(draft):
        return True
    # Also detect edits made by the older editor before this local-save protocol.
    snapshot = mapping(data.get("last_payload_snapshot"))
    product = mapping(mapping(snapshot.get("inventory_item")).get("product"))
    offer = mapping(snapshot.get("offer"))
    for key, value in (("title", draft.title), ("description", draft.description_html)):
        if key in product and product[key] != value:
            return True
    for key, value in (("categoryId", data.get("category_id")), ("merchantLocationKey", data.get("merchant_location_key")),
                       ("availableQuantity", draft.quantity), ("format", "FIXED_PRICE" if draft.listing_format == "fixed" else "AUCTION"),
                       ("listingDuration", data.get("listing_duration"))):
        if key in offer and text(offer[key]) != text(value):
            return True
    price = mapping(mapping(offer.get("pricingSummary")).get("price"))
    if "value" in price:
        try:
            if Decimal(str(price["value"])) != draft.price or price.get("currency") != draft.currency:
                return True
        except InvalidOperation:
            return True
    policies = mapping(offer.get("listingPolicies"))
    return any(key in policies and text(policies[key]) != text(data.get(field)) for key, field in (
        ("paymentPolicyId", "payment_policy_id"), ("fulfillmentPolicyId", "fulfillment_policy_id"), ("returnPolicyId", "return_policy_id"),
    ))


def sources(draft):
    saved = mapping(mapping(draft.generated_meta).get("editor_sources"))
    return {key: saved.get(key) or ("Item title" if key == "title" and draft.title == draft.item.title else "Saved draft; source not recorded")
            for key in (*LISTING_FIELDS, *EDITABLE_CHANNEL_FIELDS)}


def readiness(draft, metadata=None):
    metadata = metadata or editor_metadata(draft)
    data = mapping(draft.channel_data)
    category = mapping(metadata.get("category_snapshot"))
    condition = mapping(category.get("condition_policy"))
    checks = []
    targets = {"no_photos": "photos", "photos_unresolvable": "photos", "title_missing": "title",
               "title_too_long": "title", "description_missing": "description_html", "price_invalid": "price",
               "quantity_invalid": "quantity", "item_unavailable": "quantity"}
    for check in check_readiness(draft):
        # Legacy valuation comparisons and global grading are not listing metadata.
        if check.level == "fail":
            checks.append({**check.as_dict(), "field": targets.get(check.key, "description_html")})

    def add(key, ok, message, field, *, warning=False):
        checks.append({"key": key, "level": "pass" if ok else "warn" if warning else "fail", "message": message, "field": field})

    add("ebay_category", bool(data.get("category_id") and data.get("category_name") and mapping(category.get("category")).get("is_leaf") is True),
        "Choose an eBay leaf category and refresh its metadata.", "category_id")
    add("condition_metadata", isinstance(condition.get("required"), bool), "Refresh the category's condition policy.", "condition_id")
    valid_conditions = {text(row.get("conditionId")) for row in condition.get("conditions", []) if isinstance(row, dict)}
    if condition.get("required") or (valid_conditions and data.get("condition_id")):
        add("ebay_condition", text(data.get("condition_id")) in valid_conditions,
            "Choose a valid eBay condition for this category.", "condition_id")
    aspects = category.get("aspects")
    add("aspects_metadata", isinstance(aspects, list), "Refresh the category's item-specific requirements.", "item_specifics")
    filled = {text(row.get("name")).casefold() for row in draft.item_specifics if isinstance(row, dict) and text(row.get("value"))}
    for aspect in aspects or []:
        name = text(aspect.get("name"))
        add(f"aspect:{name}", name.casefold() in filled,
            f"{'Required' if aspect.get('required') is True else 'Recommended'} specific: {name}",
            "item_specifics", warning=aspect.get("required") is not True)
    for kind in ("payment", "fulfillment", "return"):
        add(f"{kind}_policy", any(row["id"] == text(data.get(f"{kind}_policy_id")) for row in metadata["policies"][kind]),
            f"Choose a saved {kind if kind != 'fulfillment' else 'postage'} policy.", f"{kind}_policy_id")
    add("merchant_location", any(row["id"] == text(data.get("merchant_location_key")) and row["verified"] for row in metadata["locations"]),
        "Choose a verified merchant location.", "merchant_location_key")
    formats = mapping(mapping(category.get("listing_types")).get("formats"))
    durations = formats.get("FIXED_PRICE_ITEM" if draft.listing_format == "fixed" else "AUCTION", [])
    add("listing_duration", text(data.get("listing_duration")) in durations,
        "Choose a valid duration for the format from refreshed category metadata.", "listing_duration")
    price = mapping(mapping(draft.generated_meta).get("price_source"))
    try:
        same_price = Decimal(str(price.get("value"))) == draft.price
    except InvalidOperation:
        same_price = False
    add("price_source", price.get("kind") in {"human_asking", "owned_evidence"} and same_price
        and price.get("currency") == draft.currency, "Confirm the price source: human asking price or human-picked evidence.", "price")
    add("metadata_age", not metadata["category_stale"] and not metadata["policies_stale"],
        "Metadata is missing or older than 7 days; refresh before final review.", "category_id", warning=True)
    return checks


def editor_context(draft, *, category_id=None):
    metadata = editor_metadata(draft, category_id=category_id)
    return {"metadata": metadata, "sources": sources(draft), "price_options": price_options(draft),
            "price_source": mapping(draft.generated_meta).get("price_source"),
            "checks": readiness(draft, metadata), "read_only": draft.is_read_only,
            "staged_local_changes": staged_changes(draft)}
