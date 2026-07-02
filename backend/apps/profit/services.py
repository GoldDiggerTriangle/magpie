from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from statistics import median
from typing import Iterable

from apps.inventory.models import InventoryItem
from apps.profit.models import ProfitSetting
from apps.research.models import Comparable


CENT = Decimal("0.01")
HUNDRED = Decimal("100")

BPF_FIXED = Decimal("0.30")
BPF_RATE_1 = Decimal("0.08")
BPF_RATE_2 = Decimal("0.06")
BPF_RATE_3 = Decimal("0.04")
BPF_BREAK_1 = Decimal("20.00")
BPF_BREAK_2 = Decimal("500.00")
BPF_BREAK_3 = Decimal("5000.00")
BPF_TOTAL_BREAK_1 = Decimal("21.90")
BPF_TOTAL_BREAK_2 = Decimal("530.70")
BPF_TOTAL_BREAK_3 = Decimal("5210.70")
BPF_CAP = Decimal("210.70")


class PriceBasis:
    BUYER_VISIBLE = "buyer_visible"
    SELLER_RECEIVES = "seller_receives"
    UNKNOWN = "unknown"


class EvidenceSource:
    OWN_SALE_EXACT = "own_sale_exact"
    OWN_SALE_SIMILAR = "own_sale_similar"
    APPROVED_COMP = "approved_comp"
    WHAT_IF = "what_if"


@dataclass(frozen=True)
class NormalizedPrice:
    seller_receives: Decimal | None
    basis_uncertain: bool
    label: str


@dataclass(frozen=True)
class FeeBreakdown:
    seller_mode: str
    seller_receives: Decimal
    buyer_visible_total: Decimal
    buyer_protection_fee: Decimal
    seller_final_value_fee: Decimal
    seller_fixed_fee: Decimal
    total_seller_fees: Decimal
    international_delivery_fee: Decimal
    basis_note: str


@dataclass(frozen=True)
class BuyCalculation:
    max_buy: Decimal
    verdict: str
    expected_profit_at_asking: Decimal | None
    roi_at_asking: Decimal | None
    net_proceeds_before_buy: Decimal
    seller_fees: Decimal
    non_buy_costs: Decimal
    evidence_source: str
    confidence_label: str
    roi_basis: str


def money(value) -> Decimal:
    return Decimal(str(value or "0")).quantize(CENT, rounding=ROUND_HALF_UP)


def parse_decimal(value, *, default: Decimal = Decimal("0")) -> Decimal:
    if value in {None, ""}:
        return default
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"Invalid decimal value: {value}") from exc


def buyer_protection_fee(seller_price) -> Decimal:
    price = parse_decimal(seller_price)
    first = min(price, BPF_BREAK_1)
    second = min(max(price - BPF_BREAK_1, Decimal("0")), BPF_BREAK_2 - BPF_BREAK_1)
    third = min(max(price - BPF_BREAK_2, Decimal("0")), BPF_BREAK_3 - BPF_BREAK_2)
    return money(BPF_FIXED + (first * BPF_RATE_1) + (second * BPF_RATE_2) + (third * BPF_RATE_3))


def buyer_visible_total(seller_price) -> Decimal:
    price = money(seller_price)
    return money(price + buyer_protection_fee(price))


def seller_price_from_buyer_visible(buyer_total) -> Decimal:
    total = parse_decimal(buyer_total)
    if total <= BPF_FIXED:
        return Decimal("0.00")
    if total <= BPF_TOTAL_BREAK_1:
        return money((total - Decimal("0.30")) / Decimal("1.08"))
    if total <= BPF_TOTAL_BREAK_2:
        return money((total - Decimal("0.70")) / Decimal("1.06"))
    if total <= BPF_TOTAL_BREAK_3:
        return money((total - Decimal("10.70")) / Decimal("1.04"))
    return money(total - BPF_CAP)


def normalize_to_seller_receives(price, basis: str) -> NormalizedPrice:
    if price in {None, ""}:
        return NormalizedPrice(None, False, "No price")
    amount = money(price)
    if basis == PriceBasis.SELLER_RECEIVES:
        return NormalizedPrice(amount, False, "Seller receives")
    if basis == PriceBasis.BUYER_VISIBLE:
        return NormalizedPrice(seller_price_from_buyer_visible(amount), False, "Buyer-visible converted via 2026 BPF inverse")
    return NormalizedPrice(None, True, "Basis uncertain")


def fees_for_seller_receives(
    *,
    seller_receives,
    seller_mode: str,
    setting: ProfitSetting,
    international: bool = False,
) -> FeeBreakdown:
    price = money(seller_receives)
    bpf = buyer_protection_fee(price) if seller_mode == ProfitSetting.SellerMode.FREE_SELLING else Decimal("0.00")
    fvf_pct = Decimal("0")
    fixed = Decimal("0")
    basis_note = "Seller price basis"
    if seller_mode == ProfitSetting.SellerMode.PRO_STARTER:
        fvf_pct = Decimal("13.400")
        basis_note = "Pro Starter seller FVF"
    elif seller_mode == ProfitSetting.SellerMode.PRO_OTHER:
        fvf_pct = Decimal(setting.pro_other_final_value_pct)
        basis_note = "Configured Pro seller FVF"
    elif seller_mode == ProfitSetting.SellerMode.LEGACY_MANUAL:
        fvf_pct = Decimal(setting.manual_final_value_pct)
        fixed = Decimal(setting.manual_fixed_fee)
        basis_note = "Manual configured fee model"
    elif seller_mode == ProfitSetting.SellerMode.FREE_SELLING:
        basis_note = "Free-selling: buyer pays BPF, seller FVF is zero"

    seller_fvf = money(price * fvf_pct / HUNDRED)
    seller_fixed = money(fixed)
    international_fee = money(price * Decimal("3.000") / HUNDRED) if international else Decimal("0.00")
    total_seller_fees = money(seller_fvf + seller_fixed + international_fee)
    buyer_total = buyer_visible_total(price) if seller_mode == ProfitSetting.SellerMode.FREE_SELLING else price
    return FeeBreakdown(
        seller_mode=seller_mode,
        seller_receives=price,
        buyer_visible_total=buyer_total,
        buyer_protection_fee=bpf,
        seller_final_value_fee=seller_fvf,
        seller_fixed_fee=seller_fixed,
        total_seller_fees=total_seller_fees,
        international_delivery_fee=international_fee,
        basis_note=basis_note,
    )


def max_buy_for_flat_profit(*, seller_receives, seller_fees, non_buy_costs, required_profit) -> Decimal:
    return money(parse_decimal(seller_receives) - parse_decimal(seller_fees) - parse_decimal(non_buy_costs) - parse_decimal(required_profit))


def max_buy_for_roi_all_in_cash(*, seller_receives, seller_fees, non_buy_costs, roi_pct) -> Decimal:
    roi = parse_decimal(roi_pct) / HUNDRED
    return money((parse_decimal(seller_receives) - parse_decimal(seller_fees)) / (Decimal("1") + roi) - parse_decimal(non_buy_costs))


def max_buy_for_roi_on_buy_price(*, net_proceeds_before_buy, roi_pct) -> Decimal:
    roi = parse_decimal(roi_pct) / HUNDRED
    return money(parse_decimal(net_proceeds_before_buy) / (Decimal("1") + roi))


def calculate_buy(
    *,
    expected_sell_price,
    price_basis: str,
    seller_mode: str,
    setting: ProfitSetting,
    target_type: str,
    flat_profit_target,
    roi_pct,
    roi_basis: str,
    postage,
    packaging,
    refurb,
    asking_price=None,
    evidence_source: str = EvidenceSource.WHAT_IF,
    confidence_label: str = "what-if (your estimate)",
) -> BuyCalculation:
    normalized = normalize_to_seller_receives(expected_sell_price, price_basis)
    if normalized.seller_receives is None:
        raise ValueError("Expected sell price needs a known basis for calculator math.")
    non_buy_costs = money(parse_decimal(postage) + parse_decimal(packaging) + parse_decimal(refurb))
    fee = fees_for_seller_receives(
        seller_receives=normalized.seller_receives,
        seller_mode=seller_mode,
        setting=setting,
    )
    net_before_buy = money(normalized.seller_receives - fee.total_seller_fees - non_buy_costs)
    if target_type == "flat":
        max_buy = max_buy_for_flat_profit(
            seller_receives=normalized.seller_receives,
            seller_fees=fee.total_seller_fees,
            non_buy_costs=non_buy_costs,
            required_profit=flat_profit_target,
        )
    elif roi_basis == ProfitSetting.RoiBasis.BUY_PRICE:
        max_buy = max_buy_for_roi_on_buy_price(
            net_proceeds_before_buy=net_before_buy,
            roi_pct=roi_pct,
        )
    else:
        max_buy = max_buy_for_roi_all_in_cash(
            seller_receives=normalized.seller_receives,
            seller_fees=fee.total_seller_fees,
            non_buy_costs=non_buy_costs,
            roi_pct=roi_pct,
        )

    asking = None if asking_price in {None, ""} else money(asking_price)
    expected_profit = None
    roi_at_asking = None
    verdict = "NO ASKING PRICE"
    if asking is not None:
        expected_profit = money(net_before_buy - asking)
        all_in_cash = asking + non_buy_costs
        if all_in_cash > 0:
            roi_at_asking = (expected_profit / all_in_cash * HUNDRED).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        band_multiplier = Decimal("1") + (Decimal(setting.maybe_band_pct) / HUNDRED)
        if asking <= max_buy:
            verdict = "BUY"
        elif asking <= money(max_buy * band_multiplier):
            verdict = "MAYBE"
        else:
            verdict = "PASS"

    return BuyCalculation(
        max_buy=max_buy,
        verdict=verdict,
        expected_profit_at_asking=expected_profit,
        roi_at_asking=roi_at_asking,
        net_proceeds_before_buy=net_before_buy,
        seller_fees=fee.total_seller_fees,
        non_buy_costs=non_buy_costs,
        evidence_source=evidence_source,
        confidence_label=confidence_label,
        roi_basis=roi_basis,
    )


def evidence_options_for_item(item: InventoryItem) -> list[dict]:
    from apps.research.pricing_evidence import evidence_rows

    rows = evidence_rows(item)
    options = []
    for row in rows:
        if row.record_type == "sale" and row.match_scope == "exact":
            confidence = "own sale - exact"
            source = EvidenceSource.OWN_SALE_EXACT
        elif row.record_type == "sale":
            confidence = "own sale - similar"
            source = EvidenceSource.OWN_SALE_SIMILAR
        else:
            confidence = "approved comp"
            source = EvidenceSource.APPROVED_COMP

        basis = getattr(row, "price_basis", PriceBasis.SELLER_RECEIVES if row.own_sale else PriceBasis.UNKNOWN)
        normalized = normalize_to_seller_receives(row.price, basis)
        options.append(
            {
                "id": row.id,
                "label": row.title or row.sku or row.source_label,
                "source": source,
                "confidence_label": confidence,
                "match_scope": row.match_scope,
                "match_reason": row.match_reason,
                "price": str(row.price) if row.price is not None else None,
                "price_basis": basis,
                "seller_receives": str(normalized.seller_receives) if normalized.seller_receives is not None else None,
                "basis_uncertain": normalized.basis_uncertain,
                "date": row.date,
            }
        )
    return options


def median_known_seller_receives(options: Iterable[dict]) -> dict | None:
    known = [option for option in options if option.get("seller_receives") and not option.get("basis_uncertain")]
    if not known:
        return None
    rank = {
        EvidenceSource.OWN_SALE_EXACT: 0,
        EvidenceSource.OWN_SALE_SIMILAR: 1,
        EvidenceSource.APPROVED_COMP: 2,
    }
    best_source = min(known, key=lambda option: rank.get(option["source"], 9))["source"]
    best = [option for option in known if option["source"] == best_source]
    values = [Decimal(option["seller_receives"]) for option in best]
    return {
        "price": str(money(median(values))),
        "price_basis": PriceBasis.SELLER_RECEIVES,
        "source": best_source,
        "confidence_label": best[0]["confidence_label"],
        "sample_size": len(best),
    }
