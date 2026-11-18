"""Owned-data fee service: immutable calendars, no external calls or rate defaults."""
from datetime import date
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import uuid

from django.core.exceptions import ValidationError
from django.db import IntegrityError, OperationalError, transaction
from django.utils import timezone

from apps.audit.services import record
from .fee_math import amount, calculate_order, rate, rounded
from .fee_models import (FeeScheduleVersion, FeePlanPeriod, FeeTierRate, FeeOrderSnapshot,
                         SaleFeeSnapshot, FeeAdjustment, fee_writes, safe_fee_value)

LEGACY_LABEL = "legacy (pre-engine), copied from existing records"
UNKNOWN = "schedule unknown"


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str, separators=(",", ":")).encode()).hexdigest()


def registry():
    return json.loads(Path(__file__).with_name("fee_categories.json").read_text(encoding="utf-8"))


def strict(data, allowed, required=()):
    if not isinstance(data, dict) or set(data) - set(allowed) or set(required) - set(data):
        raise ValueError("Missing or unsupported fee fields.")
    safe_fee_value(data)


def text(value, limit=500):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError("A non-empty source or label is required.")
    safe_fee_value(value)
    return value.strip()


def latest_version(using="default"):
    return FeeScheduleVersion.objects.using(using).filter(scope="ebay_au", marketplace="EBAY_AU", currency="AUD").order_by("-number").first()


def serialize_version(version):
    if version is None:
        return None
    periods = []
    for p in version.periods.all():
        periods.append({"plan": p.plan, "effective_from": str(p.effective_from), "effective_to": str(p.effective_to) if p.effective_to else None,
                        "per_order_fee": str(p.per_order_fee), "international_pct": str(p.international_pct), "gst_treatment": p.gst_treatment,
                        "source_note": p.source_note, "mapping": next(iter(p.rates.all())).mapping if p.rates.exists() else registry(),
                        "rates": [{"tier": r.tier, "fvf_pct": str(r.fvf_pct), "threshold": str(r.threshold), "above_pct": str(r.above_pct)} for r in p.rates.all()]})
    return {"id": str(version.pk), "number": version.number, "label": version.label, "source_url": version.source_url,
            "source_note": version.source_note, "created_at": version.created_at.isoformat(), "periods": periods,
            "marketplace": version.marketplace, "currency": version.currency}


def create_version(payload, actor=None, *, using="default"):
    strict(payload, {"previous_id", "label", "source_url", "source_note", "periods"}, {"previous_id", "label", "source_note", "periods"})
    label, source = text(payload["label"], 120), text(payload["source_note"], 2000)
    url = payload.get("source_url") or ""
    if url and (not url.startswith("https://") or "@" in url):
        raise ValueError("Use a public HTTPS source link without credentials.")
    periods = payload["periods"]
    if not isinstance(periods, list) or len(periods) > 100:
        raise ValueError("Use at most 100 confirmed plan periods.")
    prepared = []
    for p in periods:
        strict(p, {"plan", "effective_from", "effective_to", "per_order_fee", "international_pct", "gst_treatment", "source_note", "rates"},
               {"plan", "effective_from", "per_order_fee", "international_pct", "gst_treatment", "source_note", "rates"})
        if p["plan"] not in {"pro_basic", "pro_starter", "free_selling"} or p["gst_treatment"] != "inclusive":
            raise ValueError("Use a supported plan and GST-inclusive figures as confirmed by Regan.")
        start = date.fromisoformat(p["effective_from"])
        end = date.fromisoformat(p["effective_to"]) if p.get("effective_to") else None
        if end and end <= start:
            raise ValueError("End date is exclusive and must follow the start date.")
        rates = []
        if not isinstance(p["rates"], list):
            raise ValueError("Rates must be a list.")
        for r in p["rates"]:
            strict(r, {"tier", "fvf_pct", "threshold", "above_pct"}, {"tier", "fvf_pct", "threshold", "above_pct"})
            if r["tier"] not in {"tier1", "tier2", "tier3", "tier4"} or amount(r["threshold"]) <= 0:
                raise ValueError("Choose a supported tier and positive per-item threshold.")
            rates.append({"tier": r["tier"], "fvf_pct": rate(r["fvf_pct"]), "threshold": amount(r["threshold"]), "above_pct": rate(r["above_pct"])})
        if len({r["tier"] for r in rates}) != len(rates):
            raise ValueError("A tier can appear only once in a period.")
        prepared.append({"plan": p["plan"], "effective_from": start, "effective_to": end,
                         "per_order_fee": amount(p["per_order_fee"]), "international_pct": rate(p["international_pct"]),
                         "gst_treatment": "inclusive", "source_note": text(p["source_note"], 2000), "rates": rates})
    prepared.sort(key=lambda p: p["effective_from"])
    for left, right in zip(prepared, prepared[1:]):
        if left["effective_to"] is None or left["effective_to"] > right["effective_from"]:
            raise ValueError("Plan periods must not overlap.")
    try:
        with transaction.atomic(using=using), fee_writes():
            previous = latest_version(using)
            if (str(previous.pk) if previous else None) != payload["previous_id"]:
                raise ValueError("Calendar changed. Reload and review before saving a new version.")
            version = FeeScheduleVersion.objects.using(using).create(number=previous.number + 1 if previous else 1, previous=previous,
                label=label, source_url=url, source_note=source, entered_by=actor if getattr(actor, "is_authenticated", False) else None,
                fingerprint=digest(payload))
            for p in prepared:
                rates = p.pop("rates")
                period = FeePlanPeriod.objects.using(using).create(version=version, **p)
                for r in rates:
                    FeeTierRate.objects.using(using).create(period=period, mapping=registry(), **r)
            record(actor=actor, action="fee.calendar.created", target_type="fee_calendar", target_id=version.pk,
                   payload={"number": version.number, "period_count": len(prepared), "fingerprint": version.fingerprint}, using=using)
            return version
    except (IntegrityError, OperationalError):
        raise ValueError("Calendar changed. Reload before saving; no version was overwritten.") from None


def validate_order(order):
    strict(order, {"sale_date", "destination_country", "order_id", "postage", "handling", "marketplace_tax", "other_fee_base", "seller_discount", "buyer_incentives", "promoted_fee", "extra_charges", "lines"}, {"sale_date", "destination_country", "lines"})
    date.fromisoformat(order["sale_date"])
    country = order["destination_country"]
    if not isinstance(country, str) or len(country) != 2 or not country.isalpha() or country != country.upper():
        raise ValueError("Enter the two-letter delivery country, not the buyer's location.")
    if not isinstance(order["lines"], list) or not 1 <= len(order["lines"]) <= 1000:
        raise ValueError("Enter the complete order lines.")
    for line in order["lines"]:
        strict(line, {"key", "quantity", "item_total", "category_slug", "ebay_category_id", "ebay_path"}, {"key", "quantity", "item_total", "category_slug"})
        text(line["key"], 120)
        amount(line["item_total"])
        if type(line["quantity"]) is not int or not 1 <= line["quantity"] <= 10000:
            raise ValueError("Quantity must be a positive integer.")
        if line.get("ebay_path") and (not isinstance(line["ebay_path"], list) or any(not isinstance(v, str) or not v.isdigit() for v in line["ebay_path"])):
            raise ValueError("Category path must contain eBay category IDs only.")
    for k in ("postage", "handling", "marketplace_tax", "other_fee_base", "seller_discount", "buyer_incentives", "promoted_fee"):
        if k in order:
            amount(order[k])
    for extra in order.get("extra_charges", []):
        strict(extra, {"label", "amount", "source"}, {"label", "amount", "source"})
        text(extra["label"], 120)
        text(extra["source"], 500)
        amount(extra["amount"])
    return order


def evaluate_order(order, version=None, *, using="default"):
    validate_order(order)
    version = version or latest_version(using)
    day = date.fromisoformat(order["sale_date"])
    period = next((p for p in version.periods.all() if p.effective_from <= day and (p.effective_to is None or day < p.effective_to)), None) if version else None
    if period is None:
        unknown = calculate_order({**order, "lines": [{**l, "tier": None} for l in order["lines"]]}, {"per_order_fee": "0", "international_pct": "0"}, {})
        for line in unknown["lines"].values():
            line["components"] = {}
        unknown.update(state=UNKNOWN, label=UNKNOWN, version_id=str(version.pk) if version else None)
        return unknown, version, None
    if period.plan != "pro_basic":
        return {"state": "plan restriction", "label": "This period does not include Pro Basic API access; this is not a reconnect error.", "fee_total": None, "lines": {}, "version_id": str(version.pk)}, version, period
    mappings = next(iter(period.rates.all()), None)
    mapping = mappings.mapping.get("categories", {}) if mappings else registry()["categories"]
    rates = {r.tier: {"fvf_pct": str(r.fvf_pct), "threshold": str(r.threshold), "above_pct": str(r.above_pct)} for r in period.rates.all()}
    expanded = {**order, "lines": []}
    conflicts, unchecked = [], []
    for line in order["lines"]:
        m = mapping.get(line["category_slug"])
        roots = {root for entry in mapping.values() if m and entry["tier"] == m["tier"] for root in entry["roots"]}
        path = set(line.get("ebay_path") or []) | {str(line.get("ebay_category_id") or "")}
        conflict = bool(m and line.get("ebay_category_id") and line.get("ebay_path") and not path.intersection(roots))
        unverified = bool(m and line.get("ebay_category_id") and not line.get("ebay_path") and not path.intersection(roots))
        if conflict:
            conflicts.append(line["key"])
        if unverified:
            unchecked.append(line["key"])
        expanded["lines"].append({**line, "tier": m["tier"] if m and not conflict and not unverified else None})
    result = calculate_order(expanded, {"per_order_fee": str(period.per_order_fee), "international_pct": str(period.international_pct)}, rates)
    result.update(version_id=str(version.pk), period_id=str(period.pk), plan=period.plan, category_conflicts=conflicts, category_unverified=unchecked)
    if conflicts:
        result["label"] = "Selected eBay category conflicts with the configured Magpie tier; check category mapping."
    elif unchecked:
        result["label"] = "Selected eBay category could not be checked from saved metadata; fee rate not configured."
    return result, version, period


def snapshot_for(sale):
    try:
        return sale.fee_snapshot
    except SaleFeeSnapshot.DoesNotExist:
        return None


def effective_result(snapshot):
    result = dict(snapshot.result)
    adjustments = list(snapshot.adjustments.all())
    if adjustments and result.get("fees") is not None:
        delta = sum((a.amount for a in adjustments), Decimal(0))
        result["fees"] = str(rounded(Decimal(result["fees"]) + delta))
        if result.get("realised_profit") is not None:
            result["realised_profit"] = str(rounded(Decimal(result["realised_profit"]) - delta))
            if result.get("total_costs") and Decimal(result["total_costs"]) > 0:
                result["all_in_roi"] = str(rounded(Decimal(result["realised_profit"]) / Decimal(result["total_costs"]) * 100))
        result["fee_provenance"] = "adjusted"
    return result


def capture_sale(sale, fee_inputs=None, *, actual_known=True, line_key=None):
    from apps.profit.ledger import cost_components_for_sale, stringify_money_dict
    using = sale._state.db or "default"
    costs, cost_state, warning = cost_components_for_sale(sale)
    version = None
    total = Decimal(sale.actual_fees_total) if actual_known else None
    provenance = "actual_recorded" if actual_known else UNKNOWN
    components = dict(sale.actual_fee_breakdown) if actual_known else {}
    order_snapshot = None
    revenue = Decimal(sale.sale_price)
    calculated = None
    if fee_inputs is not None:
        calculated, version, period = evaluate_order(fee_inputs, latest_version(using), using=using)
        key = str(line_key or sale.ebay_line_item_id or sale.pk)
        supplied = next((l for l in fee_inputs["lines"] if l["key"] == key), None)
        if supplied is None or supplied["quantity"] != sale.quantity or amount(supplied["item_total"]) != sale.sale_price:
            raise ValueError("The complete order must match this sale's quantity and item amount.")
        line = calculated.get("lines", {}).get(key)
        if line is not None:
            revenue = Decimal(line["revenue"])
        identity = str(fee_inputs.get("order_id") or sale.ebay_order_id or sale.pk)
        with fee_writes():
            order_snapshot, _ = FeeOrderSnapshot.objects.using(using).get_or_create(channel=sale.channel, order_identity=identity,
                defaults={"version": version, "period": period, "sale_date": sale.sale_date, "inputs": fee_inputs, "result": calculated, "fingerprint": digest(fee_inputs)})
        if order_snapshot.fingerprint != digest(fee_inputs):
            raise ValueError("Order was captured with different inputs. Record an explicit audited correction.")
        if not actual_known:
            total = Decimal(line["fee_total"]) if line is not None and line["fee_total"] is not None else None
            provenance = "calculated" if total is not None else calculated["state"]
            components = line["components"] if line is not None else {}
    known_cost = sum(costs.values(), Decimal(0)) if cost_state == "known" else None
    profit = rounded(revenue - total - known_cost) if total is not None and known_cost is not None else None
    result = {"revenue": str(rounded(revenue)), "fees": str(rounded(total)) if total is not None else None, "fee_provenance": provenance,
              "total_costs": str(rounded(known_cost)) if known_cost is not None else None, "realised_profit": str(profit) if profit is not None else None,
              "all_in_roi": str(rounded(profit / known_cost * 100)) if profit is not None and known_cost else None,
              "cost_state": cost_state, "cost_warning": warning, "cost_components": stringify_money_dict(costs), "price_basis": "seller_receives"}
    # Date inputs are captured with the same result, not silently re-read later.
    from apps.profit.ledger import acquisition_date_for_item, days_held_for
    acquired, date_basis = acquisition_date_for_item(sale.item if sale.item_id else None)
    held, held_basis = days_held_for(acquired, sale.sale_date)
    result.update(acquired_date=str(acquired) if acquired else None, acquisition_date_basis=date_basis, days_held=held, days_held_basis=held_basis)
    with fee_writes():
        return SaleFeeSnapshot.objects.using(using).create(sale=sale, order=order_snapshot, version=version, provenance=provenance, basis="seller_receives",
            label="Actual recorded fees" if actual_known else calculated["label"] if calculated else UNKNOWN,
            inputs={"sale_price": str(sale.sale_price), "quantity": sale.quantity, "actual_fees_total": str(sale.actual_fees_total) if actual_known else None},
            components=components, result=result)


def adjust_fee(snapshot, payload, actor=None):
    strict(payload, {"amount", "reason", "provenance"}, {"amount", "reason", "provenance"})
    if payload["provenance"] not in {"actual_recorded", "human_correction"}:
        raise ValueError("Choose recorded or human-correction provenance.")
    delta = amount(payload["amount"], signed=True)
    with transaction.atomic(), fee_writes():
        snapshot = SaleFeeSnapshot.objects.select_for_update().get(pk=snapshot.pk)
        old = effective_result(snapshot)
        if old.get("fees") is None or Decimal(old["fees"]) + delta < 0:
            raise ValueError("A correction requires known fees and cannot make the total negative.")
        obj = FeeAdjustment.objects.create(snapshot=snapshot, amount=delta, reason=text(payload["reason"], 1000),
            provenance=payload["provenance"], actor=actor if getattr(actor, "is_authenticated", False) else None,
            components={"fee_delta": str(delta)})
        record(actor=actor, action="fee.adjusted", target_type="sale", target_id=snapshot.sale_id,
               payload={"adjustment_id": str(obj.pk), "fee_delta": str(delta), "provenance": obj.provenance})
        return effective_result(snapshot)


def freeze_legacy_copies(document):
    """Copy a pre-upgrade capture. Never run the new engine over historical sales."""
    from apps.sales.models import SaleRecord
    copies = document["legacy_copies"]
    with transaction.atomic(), fee_writes():
        if SaleFeeSnapshot.objects.exists():
            raise ValueError("Legacy freeze requires an empty snapshot table.")
        if {str(s.pk) for s in SaleRecord.objects.all()} != {c["sale_id"] for c in copies}:
            raise ValueError("Legacy sale set changed; stop for owner review.")
        for c in copies:
            sale = SaleRecord.objects.get(pk=c["sale_id"])
            if str(sale.actual_fees_total) != c["actual_fees_total"] or sale.estimated_fee_snapshot != c["estimated_fee_snapshot"] or sale.actual_fee_breakdown != c["actual_fee_breakdown"]:
                raise ValueError("Legacy figures changed; no snapshot was copied.")
        for c in copies:
            result = dict(c["result"])
            result["seller_mode"] = "legacy_unverified"
            result["seller_mode_basis"] = "legacy_pre_engine_copy"
            SaleFeeSnapshot.objects.create(sale_id=c["sale_id"], provenance="legacy_copy", basis="legacy_pre_engine", label=LEGACY_LABEL,
                inputs={"actual_fees_total": c["actual_fees_total"], "actual_fee_breakdown": c["actual_fee_breakdown"], "estimated_fee_snapshot": c["estimated_fee_snapshot"]},
                components=c["actual_fee_breakdown"], result=result)
    return len(copies)


def fee_order_from_owned(line):
    """Project existing order data only. Missing/ambiguous totals stay uncalculated.

    No new Fulfilment request or TAX_BREAKDOWN query is introduced. A domestic
    forwarding warehouse is not the international delivery destination.
    """
    from apps.inventory.models import InventoryItem
    from apps.ebay.order_sync import normalize_order
    order = (line.raw or {}).get("order") or {}
    summary = order.get("pricingSummary") or {}
    instructions = order.get("fulfillmentStartInstructions") or []
    if len(instructions) != 1 or not isinstance(summary, dict):
        return None
    instruction = instructions[0]
    destination = instruction.get("finalDestinationAddress") if instruction.get("ebaySupportedFulfillment") else ((instruction.get("shippingStep") or {}).get("shipTo") or {}).get("contactAddress")
    country = (destination or {}).get("countryCode")
    if not country:
        return None
    def known_money(value):
        if not isinstance(value, dict) or value.get("currency") != "AUD" or "value" not in value:
            raise ValueError
        return amount(value["value"], signed=True)
    try:
        shipping = known_money(summary["deliveryCost"])
        if summary.get("deliveryDiscount"):
            shipping -= abs(known_money(summary["deliveryDiscount"]))
        tax = known_money(summary["tax"])  # Absent tax metadata is not proof of zero tax.
        if tax and not all("ebayCollectAndRemitTaxes" in l for l in order.get("lineItems", [])):
            return None
        remitted = sum((known_money(t["amount"]) for l in order.get("lineItems", []) for t in l.get("ebayCollectAndRemitTaxes", [])), Decimal(0))
        if tax != remitted:
            return None
        lines, discount = [], Decimal(0)
        for owned in normalize_order(order):
            raw = owned.raw["line"]
            gross = known_money(raw["lineItemCost"])
            if raw.get("discountedLineItemCost"):
                discount += gross - known_money(raw["discountedLineItemCost"])
            item = InventoryItem.objects.select_related("category").filter(sku=owned.sku).first()
            category = item.category if item and item.category_id else None
            lines.append({"key": owned.line_item_id, "quantity": owned.quantity, "item_total": str(gross), "category_slug": (category.profile_key or category.slug) if category else "unknown"})
        summary_discount = abs(known_money(summary["priceDiscount"])) if summary.get("priceDiscount") else Decimal(0)
        if summary_discount != discount:
            return None
        projected = {"sale_date": str(line.sale_date), "destination_country": str(country), "order_id": line.order_id,
                     "postage": str(shipping), "marketplace_tax": str(tax), "seller_discount": str(discount), "lines": lines}
        validate_order(projected)
        return projected
    except (ValueError, KeyError, TypeError, ValidationError):
        return None
