from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from statistics import median
from typing import Protocol

from apps.research.models import Comparable
from apps.valuation.services import get_spot


CENT = Decimal("0.01")
TROY_OUNCE_GRAMS = Decimal("31.1034768")


def to_decimal(value, field_name: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be a number.") from exc


def positive_decimal(value, field_name: str) -> Decimal:
    number = to_decimal(value, field_name)
    if number <= 0:
        raise ValueError(f"{field_name} must be greater than zero.")
    return number


def money(value: Decimal | None) -> Decimal | None:
    if value is None:
        return None
    return value.quantize(CENT)


def price_per_troy_ounce_to_price_per_gram(value) -> Decimal:
    return to_decimal(value, "provider_price") / TROY_OUNCE_GRAMS


def karat_to_fineness(karat) -> Decimal:
    karat_decimal = positive_decimal(karat, "karat")
    if karat_decimal > Decimal("24"):
        raise ValueError("karat must be between 1 and 24.")
    return karat_decimal / Decimal("24")


def fineness_from_inputs(inputs: dict) -> Decimal:
    fineness_value = inputs.get("fineness")
    if fineness_value is not None and fineness_value != "":
        fineness = positive_decimal(fineness_value, "fineness")
        if fineness > Decimal("1"):
            raise ValueError("fineness must be no greater than 1.")
        return fineness
    karat_value = inputs.get("karat")
    if karat_value is None or karat_value == "":
        raise ValueError("Either fineness or karat is required.")
    return karat_to_fineness(karat_value)


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
        weight = positive_decimal(inputs.get("weight_g"), "weight_g")
        fineness = fineness_from_inputs(inputs)
        spot = positive_decimal(inputs.get("spot_price_per_g"), "spot_price_per_g")
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
        metal = str(inputs.get("metal") or "gold").strip().lower()
        currency = str(inputs.get("currency") or "AUD").strip().upper()
        weight = positive_decimal(inputs.get("weight_g"), "weight_g")
        fineness = fineness_from_inputs(inputs)
        quote = get_spot(metal, currency)
        intrinsic = money(weight * fineness * quote.price_per_gram)
        buy_margin = to_decimal(inputs.get("buy_margin_pct", 0), "buy_margin_pct")
        fast_sale = money(intrinsic * (Decimal("1") - (buy_margin / Decimal("100"))))

        inputs.update(
            {
                "metal": metal,
                "currency": quote.currency,
                "normalized_price_per_g": str(quote.price_per_gram),
                "provider_price": str(quote.provider_price),
                "provider_units": quote.provider_units,
                "source": quote.source,
                "as_of": quote.as_of.isoformat(),
                "fetched_at": quote.fetched_at.isoformat(),
                "cache_hit": quote.cache_hit,
                "weight_g": str(weight),
                "fineness": str(fineness),
                "calculated_intrinsic_value": str(intrinsic),
            }
        )

        return EstimateResult(
            low=intrinsic,
            median=intrinsic,
            high=intrinsic,
            suggested=intrinsic,
            fast_sale=fast_sale,
            patient=intrinsic,
            min_acceptable=None,
        )


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

