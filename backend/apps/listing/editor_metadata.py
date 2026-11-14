"""Chosen-category metadata and account policies, never marketplace listings."""

from copy import deepcopy
from datetime import timedelta
from decimal import Decimal, InvalidOperation
import re

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

import integrations.ebay as ebay
from apps.ebay.models import EbayAccountSnapshot, MerchantLocation
from apps.ebay.services import get_app_access_token, refresh_account_snapshot
from apps.listing.models import ListingDraft


MARKETPLACE = "EBAY_AU"
METADATA_KEY = "editor_metadata"


def mapping(value):
    return value if isinstance(value, dict) else {}


def text(value):
    return str(value or "").strip()


def humanize(value):
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", text(value)).replace("_", " ")


def flag(value):
    return value if isinstance(value, bool) else {"true": True, "false": False}.get(text(value).lower())


def money_term(value):
    value = mapping(value)
    amount = value.get("value")
    try:
        amount = Decimal(str(amount))
        if not amount.is_finite():
            raise InvalidOperation
    except InvalidOperation:
        return "charge not recorded"
    if amount == 0:
        return "Free"
    currency = text(value.get("currency"))
    prefix = {"AUD": "$", "USD": "US$", "NZD": "NZ$"}.get(currency)
    return f"{prefix}{amount:,.2f}" if prefix else f"{amount:,.2f} {currency or '(currency not recorded)'}"


def shipping_charge(option, service):
    if flag(service.get("freeShipping")) is True:
        return "Free"
    if option.get("costType") == "CALCULATED":
        return "Calculated postage"
    return money_term(service.get("shippingCost"))


def domestic_headline(policy):
    for option in policy.get("shippingOptions") or []:
        if not isinstance(option, dict) or option.get("optionType") != "DOMESTIC":
            continue
        for service in option.get("shippingServices") or []:
            if isinstance(service, dict):
                return shipping_charge(option, service)
    return ""


def period(value):
    value = mapping(value)
    return f"{value['value']} {text(value.get('unit')).lower()}" if value.get("value") is not None and value.get("unit") else "not recorded"


def policy_terms(kind, policy):
    terms = []
    if kind == "fulfillment":
        options = policy.get("shippingOptions") or []
        for option in options:
            if not isinstance(option, dict):
                continue
            scope = humanize(option.get("optionType")).title()
            for service in option.get("shippingServices") or []:
                if not isinstance(service, dict):
                    continue
                charge = shipping_charge(option, service)
                service_name = humanize(text(service.get("shippingServiceCode")).removeprefix("AU_"))
                terms.append(f"{scope}: {service_name or 'service not recorded'} - {charge}")
                if service.get("additionalShippingCost") is not None and money_term(service["additionalShippingCost"]) != "Free":
                    terms.append(f"Additional item: {money_term(service['additionalShippingCost'])}")
            if option.get("handlingTime"):
                terms.append(f"Handling: {period(option['handlingTime'])}")
        if not any(" - " in line for line in terms):
            terms.append("Shipping services and charges not recorded")
        if policy.get("handlingTime"):
            terms.append(f"Handling: {period(policy['handlingTime'])}")
        elif not any(line.startswith("Handling:") for line in terms):
            terms.append("Handling time not recorded")
        if flag(policy.get("localPickup")) is True or flag(policy.get("pickupDropOff")) is True:
            terms.append("Local pickup offered")
    elif kind == "return":
        accepted = flag(policy.get("returnsAccepted"))
        terms.append("Returns accepted" if accepted is True else "Returns not accepted" if accepted is False else "Return acceptance not recorded")
        if accepted is not False:
            terms.append(f"Return window: {period(policy.get('returnPeriod'))}")
            terms.append(f"Return postage payer: {humanize(policy.get('returnShippingCostPayer')) or 'not recorded'}")
        if policy.get("refundMethod"):
            terms.append(f"Refund: {humanize(policy['refundMethod'])}")
    else:
        immediate = flag(policy.get("immediatePay"))
        terms.append("Immediate payment required" if immediate is True else "Immediate payment not required" if immediate is False else "Payment timing not recorded")
        methods = [humanize(row.get("paymentMethodType")) for row in policy.get("paymentMethods") or [] if isinstance(row, dict) and row.get("paymentMethodType")]
        terms.append("Payment methods: " + (", ".join(methods) if methods else "not supplied by snapshot"))
    if text(policy.get("description")):
        terms.append(text(policy["description"]))
    return terms


def policy_options(kind, policies, fetched_at):
    result = []
    for policy in policies or []:
        if not isinstance(policy, dict) or policy.get("marketplaceId", MARKETPLACE) != MARKETPLACE:
            continue
        policy_id = text(policy.get(f"{kind}PolicyId"))
        if not policy_id:
            continue
        terms = policy_terms(kind, policy)
        result.append({
            "id": policy_id, "name": text(policy.get("name")) or policy_id,
            "terms": terms, "summary": " | ".join(terms),
            "headline": domestic_headline(policy) if kind == "fulfillment" else "",
            "fetched_at": fetched_at, "provenance": "eBay Account API saved snapshot",
        })
    return result


def stale(fetched_at):
    try:
        stamp = parse_datetime(text(fetched_at)) if fetched_at else None
    except ValueError:
        stamp = None
    if stamp and timezone.is_naive(stamp):
        stamp = timezone.make_aware(stamp)
    return stamp is None or stamp < timezone.now() - timedelta(days=7)


def cached_category(draft, category_id):
    data = mapping(draft.channel_data)
    cached = mapping(mapping(mapping(data.get(METADATA_KEY)).get("categories")).get(category_id))
    if cached:
        return deepcopy(cached)
    # Phase 0's real staging snapshot is already local evidence. Never refetch on GET.
    staged = mapping(data.get("last_payload_snapshot"))
    if not category_id or text(mapping(staged.get("offer")).get("categoryId")) != category_id:
        return None
    aspects = mapping(staged.get("aspects"))
    condition = mapping(staged.get("condition_policy"))
    fetched = condition.get("fetched_at") or aspects.get("fetched_at")
    return {
        "category": {"category_id": category_id, "category_name": text(data.get("category_name")), "category_tree_id": text(data.get("category_tree_id")), "is_leaf": True},
        "aspects": aspects.get("aspects") if isinstance(aspects.get("aspects"), list) else None,
        "condition_policy": condition if condition.get("category_id") == category_id and condition.get("marketplace") == MARKETPLACE else None,
        "listing_types": None,
        "fetched_at": fetched, "provenance": "Saved eBay staging metadata (last known)",
    }


def editor_metadata(draft, *, category_id=None):
    data = mapping(draft.channel_data)
    category_id = text(category_id if category_id is not None else data.get("category_id"))
    category = cached_category(draft, category_id)
    environment = ebay.effective_environment()
    account = EbayAccountSnapshot.objects.filter(environment=environment).first()
    fetched = account.fetched_at.isoformat() if account and account.fetched_at else None
    policies = {
        kind: policy_options(kind, getattr(account, f"{kind}_policies", []), fetched)
        for kind in ("payment", "fulfillment", "return")
    }
    locations = [
        {"id": row.merchant_location_key, "name": row.name,
         "address": ", ".join(part for part in [row.city, row.state, row.postal_code, row.country] if part),
         "fetched_at": row.fetched_at.isoformat() if row.fetched_at else None,
         "provenance": "Saved merchant-location record", "verified": row.created_on_ebay}
        for row in MerchantLocation.objects.filter(environment=environment)
    ]
    return {
        "category_id": category_id, "category_snapshot": category,
        "category_stale": stale(category.get("fetched_at")) if category else True,
        "policies": policies, "policies_fetched_at": fetched,
        "policies_provenance": "eBay Account API saved snapshot", "policies_stale": stale(fetched),
        "locations": locations,
        "category_search": mapping(mapping(data.get(METADATA_KEY)).get("search")),
    }


def refresh_editor_metadata(draft, *, category_id="", query="", actor=None):
    draft.assert_editable()
    category_id, query = text(category_id), text(query)
    adapter = ebay.get_ebay_taxonomy_adapter(access_token=get_app_access_token())
    fetched = timezone.now().isoformat()
    category = None
    search = None
    if query:
        search = {"query": query, "suggestions": adapter.suggest_categories(q=query),
                  "fetched_at": fetched, "provenance": "eBay Taxonomy API GET"}
    if category_id:
        details = adapter.category_details(category_id=category_id)
        if details.get("is_leaf") is not True:
            from django.core.exceptions import ValidationError
            raise ValidationError({"category_id": "Choose a leaf eBay category."})
        category = {
            "category": details, "aspects": adapter.item_aspects(category_id=category_id),
            "condition_policy": {**adapter.item_condition_policy(category_id=category_id), "marketplace": MARKETPLACE, "fetched_at": fetched},
            "listing_types": adapter.listing_type_policy(category_id=category_id),
            "fetched_at": fetched, "provenance": "eBay Taxonomy + Sell Metadata API GETs",
        }
    if not query:
        refresh_account_snapshot(actor=actor)
    # Network work is complete before the short local update. Preserve any newer
    # human edits; refreshing metadata must never replace listing field values.
    with transaction.atomic():
        current = ListingDraft.objects.select_for_update().get(pk=draft.pk)
        current.assert_editable()
        data = deepcopy(mapping(current.channel_data))
        metadata = deepcopy(mapping(data.get(METADATA_KEY)))
        categories = deepcopy(mapping(metadata.get("categories")))
        if category is not None:
            categories.pop(category_id, None)
            categories[category_id] = category
            metadata["categories"] = dict(list(categories.items())[-8:])
        if search is not None:
            metadata["search"] = search
        data[METADATA_KEY] = metadata
        current.channel_data = data
        current.save(update_fields=["channel_data", "updated_at"])
    return current
