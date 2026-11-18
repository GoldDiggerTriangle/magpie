"""Pure local fee maths. Rates are inputs, never production defaults."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

RULE = "unit-largest-remainder-v1"


def amount(value, *, signed=False):
    try:
        result = Decimal(str(value))
        if not result.is_finite() or abs(result) > Decimal("9999999999") or (not signed and result < 0):
            raise ValueError
        if result != result.quantize(Decimal("0.01")):
            raise ValueError
        return result.quantize(Decimal("0.01"))
    except (ValueError, InvalidOperation, TypeError):
        raise ValueError("Enter a finite amount to the cent.") from None


def rate(value):
    try:
        result = Decimal(str(value))
        if not result.is_finite() or result < 0 or result > 100 or result != result.quantize(Decimal("0.000001")):
            raise ValueError
        return result
    except (ValueError, InvalidOperation, TypeError):
        raise ValueError("Enter a percentage between zero and 100, up to six decimals.") from None


def rounded(value):
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def allocate(total, weights):
    """Largest remainder, input-key order breaks ties; all cents are conserved."""
    total = amount(total)
    if not weights:
        if total:
            raise ValueError("Cannot allocate money without items.")
        return []
    weights = [Decimal(w) for w in weights]
    if not sum(weights):
        weights = [Decimal(1)] * len(weights)
    exact = [total * 100 * w / sum(weights) for w in weights]
    cents = [int(v) for v in exact]
    for i in sorted(range(len(cents)), key=lambda i: (-(exact[i] - cents[i]), i))[:int(total * 100) - sum(cents)]:
        cents[i] += 1
    return [Decimal(c) / 100 for c in cents]


def calculate_order(order, period, rates):
    lines = sorted(order["lines"], key=lambda line: line["key"])
    units = []
    for line in lines:
        if type(line["quantity"]) is not int or not 1 <= line["quantity"] <= 10000:
            raise ValueError("Quantity must be a positive integer, at most 10000.")
        for i, price in enumerate(allocate(amount(line["item_total"]), [1] * line["quantity"])):
            units.append({"key": line["key"], "tier": line.get("tier"), "price": price, "index": i})
    if not units or len(units) > 10000:
        raise ValueError("An order needs between one and 10000 units.")
    if len({l["key"] for l in lines}) != len(lines):
        raise ValueError("Order line keys must be unique.")
    prices = [u["price"] for u in units]
    discount = amount(order.get("seller_discount", "0"))
    if discount > sum(prices):
        raise ValueError("Seller discount exceeds the item total.")
    discounts = allocate(discount, prices)
    net = [p - d for p, d in zip(prices, discounts)]
    postage = allocate(amount(order.get("postage", "0")) + amount(order.get("handling", "0")), net)
    tax = allocate(amount(order.get("marketplace_tax", "0")), net)
    extras = allocate(amount(order.get("other_fee_base", "0")), net)
    bases = [p + s + t + e for p, s, t, e in zip(net, postage, tax, extras)]
    fixed = allocate(amount(period["per_order_fee"]), bases)
    promoted = allocate(amount(order.get("promoted_fee", "0")), bases)
    extra_fees = allocate(sum((amount(e["amount"], signed=True) for e in order.get("extra_charges", [])), Decimal(0)), bases)
    international = order.get("destination_country") != "AU"
    result = {}
    for i, unit in enumerate(units):
        row = result.setdefault(unit["key"], {"fee_total": Decimal(0), "revenue": Decimal(0), "fee_base": Decimal(0), "components": {k: Decimal(0) for k in ("final_value_fee", "per_order_fee", "international_fee", "promoted_fee", "extra_charges")}, "state": "calculated"})
        row["revenue"] += net[i] + postage[i] + extras[i]  # Marketplace-collected tax is not seller revenue.
        row["fee_base"] += bases[i]
        r = rates.get(unit["tier"])
        if r is None:
            row["state"] = "fee rate not configured"
            continue
        threshold = amount(r["threshold"])
        fvf = rounded(min(bases[i], threshold) * rate(r["fvf_pct"]) / 100 + max(bases[i] - threshold, Decimal(0)) * rate(r["above_pct"]) / 100)
        intl = rounded(bases[i] * rate(period["international_pct"]) / 100) if international else Decimal(0)
        components = {"final_value_fee": fvf, "per_order_fee": fixed[i], "international_fee": intl, "promoted_fee": promoted[i], "extra_charges": extra_fees[i]}
        for k, v in components.items():
            row["components"][k] += v
        row["fee_total"] += sum(components.values())
    for row in result.values():
        row["components"] = {k: str(rounded(v)) for k, v in row["components"].items()}
        row["fee_total"] = str(rounded(row["fee_total"])) if row["state"] == "calculated" else None
        row["revenue"] = str(rounded(row["revenue"]))
        row["fee_base"] = str(rounded(row["fee_base"]))
    known = all(r["fee_total"] is not None for r in result.values())
    return {"state": "calculated" if known else "fee rate not configured", "label": "Calculated fees - not evidence of what eBay charged", "rule": RULE,
            "lines": result, "fee_total": str(rounded(sum((Decimal(r["fee_total"]) for r in result.values()), Decimal(0)))) if known else None,
            "gst_added": "0.00", "buyer_incentives_in_fee_base": False}
