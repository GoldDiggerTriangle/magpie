"""D-135 human-chosen defaults. Opening a draft never mutates this registry."""

from copy import deepcopy
from hashlib import sha256
import json
from types import SimpleNamespace

from django.core.exceptions import ValidationError
from django.utils.dateparse import parse_datetime

import integrations.ebay as ebay
from apps.ebay.models import EbayAccountSnapshot, EbayCredential, MerchantLocation
from apps.listing.editor_metadata import METADATA_KEY, MARKETPLACE, editor_metadata, mapping, text
from apps.listing.models import CategoryListingDefaults, ListingDraft


# Category ID/name/tree are one category choice, not independently inferred defaults.
DEFAULT_FIELDS = ("category_id", "category_name", "category_tree_id", "condition_id",
                  "payment_policy_id", "fulfillment_policy_id", "return_policy_id",
                  "merchant_location_key", "listing_format", "listing_duration")
FIELD_LABELS = {"category_id": "eBay category", "category_name": "eBay category name", "category_tree_id": "eBay category tree",
                "condition_id": "Condition", "payment_policy_id": "Payment policy", "fulfillment_policy_id": "Postage policy",
                "return_policy_id": "Return policy", "merchant_location_key": "Merchant location", "listing_format": "Format", "listing_duration": "Duration"}


def normalize_values(values):
    if not isinstance(values, dict) or set(values) - set(DEFAULT_FIELDS):
        raise ValidationError("Only D-135 listing defaults are accepted; never price, quantity or item specifics.")
    if any(not isinstance(value, str) or len(value) > 400 for value in values.values()):
        raise ValidationError("Default values must be text of at most 400 characters; use blank to clear.")
    result = {key: value.strip() for key, value in values.items() if value.strip()}
    if result.get("listing_format", "") not in {"", "fixed", "auction"}:
        raise ValidationError("Format must be fixed, auction or blank.")
    for key in ("category_id", "category_tree_id", "condition_id"):
        if result.get(key) and not result[key].isdecimal():
            raise ValidationError(f"{FIELD_LABELS[key]} must be a numeric ID.")
    if not result.get("category_id"):
        for key in ("category_name", "category_tree_id", "condition_id"):
            result.pop(key, None)
    return result


def revision(values):
    return sha256(json.dumps(values, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def defaults_row(category):
    return CategoryListingDefaults.objects.filter(category=category, environment=ebay.effective_environment(), marketplace=MARKETPLACE).first()


def snapshot_time(value):
    try:
        stamp = parse_datetime(text(value))
        return stamp.timestamp() if stamp else 0
    except (ValueError, TypeError, OverflowError):
        return 0


def latest_category(category_id, metadata=None):
    """Prefer the latest complete snapshot; a newer partial/failed refresh is not invalidity."""
    candidates = [mapping(mapping(metadata).get("categories")).get(category_id)]
    for channel in ListingDraft.objects.filter(channel="ebay_au").values_list("channel_data", flat=True):
        candidate = mapping(mapping(mapping(channel).get(METADATA_KEY)).get("categories")).get(category_id)
        if candidate:
            candidates.append(candidate)
    candidates = [row for row in candidates if isinstance(row, dict) and snapshot_time(row.get("fetched_at"))
                  and text(mapping(row.get("category")).get("category_id")) == category_id
                  and row.get("environment", ebay.effective_environment()) == ebay.effective_environment()
                  and row.get("marketplace", MARKETPLACE) == MARKETPLACE]
    candidates.sort(key=lambda row: snapshot_time(row.get("fetched_at")), reverse=True)
    def complete(row):
        if mapping(row.get("category")).get("is_leaf") is False:
            return True  # A confirmed non-leaf alone proves the category choice invalid.
        condition = mapping(row.get("condition_policy"))
        listing_types = mapping(row.get("listing_types"))
        formats = listing_types.get("formats")
        return (isinstance(mapping(row.get("category")).get("is_leaf"), bool)
                and text(condition.get("category_id", category_id)) == category_id
                and condition.get("marketplace", MARKETPLACE) == MARKETPLACE
                and text(listing_types.get("category_id", category_id)) == category_id
                and isinstance(condition.get("required"), bool) and isinstance(condition.get("conditions"), list)
                and isinstance(formats, dict) and all(isinstance(v, list) for v in formats.values())
                and isinstance(row.get("aspects"), list))
    return deepcopy(next((row for row in candidates if complete(row)), candidates[0] if candidates else None))


def defaults_metadata(values, saved_metadata=None):
    data = deepcopy(mapping(saved_metadata))
    category_id = text(values.get("category_id"))
    candidate = latest_category(category_id, data)
    if candidate:
        data.setdefault("categories", {})[category_id] = candidate
    virtual = SimpleNamespace(channel_data={**values, METADATA_KEY: data})
    return editor_metadata(virtual), data


def evaluate_defaults(values, metadata):
    """Return a copy and per-field evidence. Stale is usable; incomplete is not invalid."""
    applied = deepcopy(values)
    checks = {}
    category = mapping(metadata.get("category_snapshot"))
    node = mapping(category.get("category"))
    stamp = category.get("fetched_at")
    def note(field, state, reason, fetched_at=stamp):
        checks[field] = {"field": field, "state": state, "message": f"{FIELD_LABELS[field]}: {reason}", "fetched_at": fetched_at}
        if state == "invalid":
            applied.pop(field, None)
    if values.get("category_id"):
        if isinstance(node.get("is_leaf"), bool):
            if not node["is_leaf"]:
                for key in ("category_id", "category_name", "category_tree_id"):
                    note(key, "invalid", "default is no longer a leaf category; left empty.")
        else:
            note("category_id", "unchecked", "couldn't check: category metadata unavailable or incomplete.")
    if values.get("condition_id"):
        if not applied.get("category_id"):
            note("condition_id", "invalid", "default category was not applied; condition left empty.")
        else:
            policy = mapping(category.get("condition_policy"))
            options = policy.get("conditions")
            if text(policy.get("category_id", values.get("category_id"))) == values.get("category_id") and policy.get("marketplace", MARKETPLACE) == MARKETPLACE and isinstance(policy.get("required"), bool) and isinstance(options, list) and all(isinstance(r, dict) and text(r.get("conditionId")) for r in options):
                if not policy["required"] and not options:
                    applied.pop("condition_id", None)
                    note("condition_id", "not_used", "not used by this category.")
                elif text(values["condition_id"]) not in {text(row.get("conditionId")) for row in options}:
                    note("condition_id", "invalid", "default is not valid for this category; left empty.")
            else:
                note("condition_id", "unchecked", "couldn't check: condition metadata unavailable or incomplete.")
    formats = mapping(mapping(category.get("listing_types")).get("formats"))
    if text(mapping(category.get("listing_types")).get("category_id", values.get("category_id"))) != text(values.get("category_id")):
        formats = {}
    kind = {"fixed": "FIXED_PRICE_ITEM", "auction": "AUCTION"}.get(values.get("listing_format"))
    if values.get("listing_format"):
        if not formats or not applied.get("category_id"):
            note("listing_format", "unchecked", "couldn't check: format metadata unavailable or incomplete.")
        elif kind not in formats or not formats[kind]:
            note("listing_format", "invalid", "default format is not supported; left empty.")
    if values.get("listing_duration"):
        if "listing_format" in checks and checks["listing_format"]["state"] == "invalid":
            note("listing_duration", "invalid", "default format was not applied; duration left empty.")
        elif not kind:
            note("listing_duration", "invalid", "no default format to pair with this duration; left empty.")
        elif not formats or not isinstance(formats.get(kind), list) or not applied.get("category_id"):
            note("listing_duration", "unchecked", "couldn't check: duration metadata unavailable or incomplete.")
        elif values["listing_duration"] not in formats[kind]:
            note("listing_duration", "invalid", "default duration is invalid for the format; left empty.")
    environment = ebay.effective_environment()
    account = EbayAccountSnapshot.objects.filter(environment=environment).first()
    credential = EbayCredential.objects.filter(environment=environment).only("created_at").first()
    account_known = bool(account and account.fetched_at and (not credential or account.fetched_at >= credential.created_at))
    for kind in ("payment", "fulfillment", "return"):
        field = f"{kind}_policy_id"
        if not values.get(field):
            continue
        policies = getattr(account, f"{kind}_policies", None) if account_known else None
        complete = isinstance(policies, list) and all(isinstance(p, dict) and text(p.get(f"{kind}PolicyId")) and text(p.get("marketplaceId")) for p in policies)
        policy = next((p for p in policies or [] if isinstance(p, dict) and text(p.get(f"{kind}PolicyId")) == values[field]), None)
        at = account.fetched_at.isoformat() if account and account.fetched_at else None
        if account_known and account.business_policies_opted_in is False:
            note(field, "invalid", "saved account is not opted into business policies; left empty.", at)
        elif complete and (not policy or policy.get("marketplaceId") != MARKETPLACE):
            note(field, "invalid", "default is not applicable to the saved account/marketplace; left empty.", at)
        elif not complete:
            note(field, "unchecked", "couldn't check: account policy snapshot unavailable, incomplete or predates reconnect.", at)
        elif policy.get("categoryTypes"):
            allowed = {text(p.get("name")) for p in policy["categoryTypes"] if isinstance(p, dict)}
            category_type = node.get("policy_category_type")
            if category_type and category_type not in allowed:
                note(field, "invalid", "default policy does not apply to this category; left empty.", at)
            elif not category_type:
                note(field, "unchecked", "couldn't check policy category applicability from this snapshot.", at)
    location = values.get("merchant_location_key")
    if location:
        rows = list(MerchantLocation.objects.filter(environment=environment))
        chosen = next((row for row in rows if row.merchant_location_key == location), None)
        if chosen and chosen.fetched_at and (not credential or chosen.fetched_at >= credential.created_at):
            if not chosen.created_on_ebay:
                note("merchant_location_key", "invalid", "default location is not verified for this account; left empty.", chosen.fetched_at.isoformat())
            elif chosen.country != "AU":
                note("merchant_location_key", "unchecked", "couldn't check this location's applicability to EBAY_AU.", chosen.fetched_at.isoformat())
        else:
            # Local location rows are not an authoritative complete account inventory.
            note("merchant_location_key", "unchecked", "couldn't check: location metadata missing or predates reconnect.", chosen.fetched_at.isoformat() if chosen and chosen.fetched_at else None)
    return applied, list(checks.values())


def apply_new_defaults(item):
    row = defaults_row(item.category)
    values = normalize_values(row.values) if row else {}
    metadata, cached = defaults_metadata(values, row.metadata if row else {})
    applied, checks = evaluate_defaults(values, metadata)
    format_value = applied.pop("listing_format", "")
    source = f"from {item.category.name} defaults" if item.category else "No category defaults"
    origins = {field: source for field in applied}
    if format_value:
        origins["listing_format"] = source
    origins["quantity"] = "Item remaining stock (total minus sold)"
    return {"listing_format": format_value, "quantity": item.quantity_remaining,
            "channel_data": {**applied, **({METADATA_KEY: cached} if cached else {})},
            "origins": origins, "checks": checks}
