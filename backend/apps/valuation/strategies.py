from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from statistics import median
from typing import Protocol

from apps.research.models import Comparable


CENT = Decimal("0.01")


def to_decimal(value, field_name: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be a number.") from exc


def money(value: Decimal | None) -> Decimal | None:
    if value is None:
        return None
    return value.quantize(CENT)


@dataclass
class EstimateResult:
    low: Decimal | None
    median: Decimal | None
    high: Decimal | None
    suggested: Decimal | None
    fast_sale: Decimal | None
    patient: Decimal | None
    min_acceptable: Decimal | None


class ValuationStrategy(Protocol):
    key: str

    def estimate(self, *, item, included_comps: list, inputs: dict) -> EstimateResult:
        ...


class CompBasedStrategy:
    key = "comp_based"

    def estimate(self, *, item, included_comps: list[Comparable], inputs: dict) -> EstimateResult:
        priced = [comp for comp in included_comps if comp.price is not None]
        sold = [comp for comp in priced if comp.kind == Comparable.Kind.SOLD]
        fallback = [
            comp
            for comp in priced
            if comp.kind in {Comparable.Kind.ACTIVE, Comparable.Kind.AUCTION_RESULT}
        ]
        selected = sold or fallback or priced
        prices = [Decimal(comp.price) for comp in selected]
        if not prices:
            return EstimateResult(None, None, None, None, None, None, None)

        low = money(min(prices))
        high = money(max(prices))
        median_price = money(Decimal(str(median(prices))))
        return EstimateResult(
            low=low,
            median=median_price,
            high=high,
            suggested=median_price,
            fast_sale=low,
            patient=high,
            min_acceptable=None,
        )


class CommodityManualStrategy:
    key = "commodity_manual"

    def estimate(self, *, item, included_comps: list, inputs: dict) -> EstimateResult:
        weight = to_decimal(inputs.get("weight_g"), "weight_g")
        fineness = to_decimal(inputs.get("fineness"), "fineness")
        spot = to_decimal(inputs.get("spot_price_per_g"), "spot_price_per_g")
        buy_margin = to_decimal(inputs.get("buy_margin_pct", 0), "buy_margin_pct")

        intrinsic = money(weight * fineness * spot)
        fast_sale = money(intrinsic * (Decimal("1") - (buy_margin / Decimal("100"))))
        return EstimateResult(
            low=intrinsic,
            median=intrinsic,
            high=intrinsic,
            suggested=intrinsic,
            fast_sale=fast_sale,
            patient=intrinsic,
            min_acceptable=None,
        )


class CommodityLiveStrategy:
    key = "commodity_live"

    def estimate(self, *, item, included_comps: list, inputs: dict) -> EstimateResult:
        raise NotImplementedError("commodity_live: Sprint 3 - wire MetalsPriceAdapter")


STRATEGIES: dict[str, ValuationStrategy] = {
    CompBasedStrategy.key: CompBasedStrategy(),
    CommodityManualStrategy.key: CommodityManualStrategy(),
    CommodityLiveStrategy.key: CommodityLiveStrategy(),
}


def get_strategy(key: str) -> ValuationStrategy:
    try:
        return STRATEGIES[key]
    except KeyError as exc:
        raise ValueError(f"Unknown valuation strategy: {key}") from exc

