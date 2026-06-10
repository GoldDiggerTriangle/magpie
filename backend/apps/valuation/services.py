from dataclasses import asdict, dataclass
from decimal import Decimal
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.valuation.models import FeeSchedule, MetalSpotCache, ValuationReport
from integrations.metals import MetalsUnavailable, SpotQuote, get_metals_adapter


CENT = Decimal("0.01")
RATIO = Decimal("0.0001")
HUNDRED = Decimal("100")


def money(value: Decimal) -> Decimal:
    return value.quantize(CENT)


def ratio(value: Decimal) -> Decimal:
    return value.quantize(RATIO)


def get_spot(metal, currency="AUD", *, force_refresh=False) -> SpotQuote:
    metal_code = str(metal or "").strip().lower()
    currency_code = str(currency or settings.METALS_BASE_CURRENCY).strip().upper()
    adapter = get_metals_adapter()
    provider = adapter.provider_name
    cached = MetalSpotCache.objects.filter(
        metal=metal_code,
        currency=currency_code,
        provider=provider,
    ).first()

    if cached is not None and not force_refresh and _is_fresh(cached):
        return _quote_from_cache(cached, cache_hit=True)

    try:
        quote = adapter.spot_price(metal_code, currency_code)
    except MetalsUnavailable:
        if cached is not None:
            return _quote_from_cache(cached, cache_hit=True)
        raise

    MetalSpotCache.objects.update_or_create(
        metal=quote.metal,
        currency=quote.currency,
        provider=quote.source,
        defaults={
            "price_per_gram": quote.price_per_gram,
            "provider_price": quote.provider_price,
            "provider_units": quote.provider_units,
            "as_of": quote.as_of,
            "fetched_at": quote.fetched_at,
        },
    )
    return quote


def serialize_spot_quote(quote: SpotQuote) -> dict:
    return {
        "metal": quote.metal,
        "currency": quote.currency,
        "price_per_gram": str(quote.price_per_gram),
        "provider_price": str(quote.provider_price),
        "provider_units": quote.provider_units,
        "source": quote.source,
        "as_of": quote.as_of.isoformat(),
        "fetched_at": quote.fetched_at.isoformat(),
        "cache_hit": quote.cache_hit,
    }


def _quote_from_cache(cache: MetalSpotCache, *, cache_hit: bool) -> SpotQuote:
    return SpotQuote(
        metal=cache.metal,
        currency=cache.currency,
        price_per_gram=cache.price_per_gram,
        provider_price=cache.provider_price,
        provider_units=cache.provider_units,
        source=cache.provider,
        as_of=cache.as_of,
        fetched_at=cache.fetched_at,
        cache_hit=cache_hit,
    )


def _is_fresh(cache: MetalSpotCache) -> bool:
    ttl = timedelta(seconds=settings.METALS_CACHE_TTL_SECONDS)
    return cache.fetched_at >= timezone.now() - ttl


@dataclass
class ProfitBreakdown:
    sale_price: Decimal
    final_value_fee: Decimal
    per_order_fee: Decimal
    promoted_fee: Decimal
    gst_on_fees: Decimal
    outbound_shipping: Decimal
    packaging: Decimal
    true_cost: Decimal
    total_deductions: Decimal
    net_profit: Decimal
    margin_pct: Decimal

    def as_serialized(self) -> dict:
        data = asdict(self)
        return {key: str(value) for key, value in data.items()}


def decimal_or_zero(value) -> Decimal:
    if value is None:
        return Decimal("0")
    return Decimal(value)


def active_fee_schedule() -> FeeSchedule | None:
    return FeeSchedule.objects.filter(is_active=True).order_by("-effective_from").first()


def true_cost_for_item(item) -> Decimal:
    return sum(
        (
            decimal_or_zero(item.acquisition_cost),
            decimal_or_zero(item.refurb_cost),
            decimal_or_zero(item.inbound_shipping_cost),
        ),
        Decimal("0"),
    )


def calculate_profit(
    *,
    sale_price,
    true_cost,
    schedule: FeeSchedule,
    outbound_shipping=None,
    packaging=None,
) -> ProfitBreakdown:
    sale = Decimal(str(sale_price))
    true_cost_decimal = Decimal(str(true_cost))
    ship = (
        Decimal(str(outbound_shipping))
        if outbound_shipping is not None
        else Decimal(schedule.default_outbound_shipping)
    )
    pack = (
        Decimal(str(packaging))
        if packaging is not None
        else Decimal(schedule.default_packaging_cost)
    )

    final_value_fee = money(
        (sale + ship) * Decimal(schedule.final_value_pct) / HUNDRED
    )
    per_order_fee = money(Decimal(schedule.per_order_fee))
    promoted_fee = money(sale * Decimal(schedule.promoted_pct) / HUNDRED)
    fees = final_value_fee + per_order_fee + promoted_fee
    gst_on_fees = money(fees * Decimal(schedule.gst_pct) / HUNDRED)
    total_deductions = money(fees + gst_on_fees + ship + pack + true_cost_decimal)
    net_profit = money(sale - total_deductions)
    margin_pct = Decimal("0") if sale == 0 else ratio(net_profit / sale)

    return ProfitBreakdown(
        sale_price=money(sale),
        final_value_fee=final_value_fee,
        per_order_fee=per_order_fee,
        promoted_fee=promoted_fee,
        gst_on_fees=gst_on_fees,
        outbound_shipping=money(ship),
        packaging=money(pack),
        true_cost=money(true_cost_decimal),
        total_deductions=total_deductions,
        net_profit=net_profit,
        margin_pct=margin_pct,
    )


@transaction.atomic
def set_current(report: ValuationReport) -> ValuationReport:
    report = (
        ValuationReport.objects.select_for_update()
        .select_related("item")
        .get(pk=report.pk)
    )
    ValuationReport.objects.filter(item=report.item, is_current=True).exclude(
        pk=report.pk
    ).update(is_current=False)
    if not report.is_current:
        report.is_current = True
        report.save(update_fields=["is_current", "updated_at"])

    item = report.item
    update_fields = ["updated_at"]
    if report.estimate_median is not None:
        item.estimated_value = report.estimate_median
        update_fields.append("estimated_value")
    if report.suggested_price is not None:
        item.target_price = report.suggested_price
        update_fields.append("target_price")
    if report.min_acceptable_price is not None:
        item.min_price = report.min_acceptable_price
        update_fields.append("min_price")
    item.save(update_fields=update_fields)
    return report
