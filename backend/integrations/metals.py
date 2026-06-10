from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone as datetime_timezone
from decimal import Decimal, InvalidOperation
import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from django.utils import timezone


TROY_OUNCE_GRAMS = Decimal("31.1034768")
SPOT_PLACES = Decimal("0.000001")
METALS_DEV_ALIASES = {"metals.dev", "metalsdev", "metals_dev"}


@dataclass(frozen=True)
class SpotQuote:
    metal: str
    currency: str
    price_per_gram: Decimal
    provider_price: Decimal
    provider_units: str
    source: str
    as_of: datetime
    fetched_at: datetime
    cache_hit: bool


class MetalsUnavailable(Exception):
    """Raised when live metals pricing cannot return a usable quote."""


class MetalsPriceAdapter(ABC):
    provider_name = "unknown"

    @abstractmethod
    def spot_price(self, metal: str, currency: str = "AUD") -> SpotQuote:
        raise NotImplementedError


class HttpMetalsPriceAdapter(MetalsPriceAdapter):
    provider_name = "metals.dev"

    def __init__(self, *, api_key: str | None = None, timeout_seconds: int | None = None):
        self.api_key = api_key if api_key is not None else settings.METALS_API_KEY
        self.timeout_seconds = (
            timeout_seconds
            if timeout_seconds is not None
            else settings.METALS_HTTP_TIMEOUT_SECONDS
        )

    def spot_price(self, metal: str, currency: str = "AUD") -> SpotQuote:
        provider = settings.METALS_PROVIDER.strip().lower()
        if provider not in METALS_DEV_ALIASES:
            raise MetalsUnavailable(f"Unsupported metals provider: {settings.METALS_PROVIDER}")
        if not self.api_key:
            raise MetalsUnavailable("METALS_API_KEY is required for live metals pricing.")

        metal_code = _normalize_metal(metal)
        currency_code = _normalize_currency(currency)
        query = urlencode(
            {
                "api_key": self.api_key,
                "metal": metal_code,
                "currency": currency_code,
                "unit": "toz",
            }
        )
        request = Request(
            f"https://api.metals.dev/v1/metal/spot?{query}",
            headers={"Accept": "application/json"},
        )

        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise MetalsUnavailable(f"Metals provider returned HTTP {exc.code}.") from exc
        except (URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise MetalsUnavailable("Metals provider request failed.") from exc

        try:
            if payload.get("status") != "success":
                raise ValueError(payload.get("error_message") or "Provider returned failure.")
            provider_price = _decimal(payload["rate"]["price"], "rate.price")
            response_currency = _normalize_currency(payload.get("currency", currency_code))
            unit = str(payload.get("unit") or "toz").lower()
            provider_units = _provider_units(response_currency, unit)
            as_of = _parse_timestamp(payload["timestamp"])
        except (KeyError, TypeError, ValueError, InvalidOperation) as exc:
            raise MetalsUnavailable("Metals provider response could not be parsed.") from exc

        return SpotQuote(
            metal=metal_code,
            currency=response_currency,
            price_per_gram=_normalize_price_per_gram(provider_price, provider_units),
            provider_price=provider_price,
            provider_units=provider_units,
            source=self.provider_name,
            as_of=as_of,
            fetched_at=timezone.now(),
            cache_hit=False,
        )


class FakeMetalsPriceAdapter(MetalsPriceAdapter):
    provider_name = "fake"

    def spot_price(self, metal: str, currency: str = "AUD") -> SpotQuote:
        now = timezone.now()
        currency_code = _normalize_currency(currency)
        provider_price = Decimal("3110.347680")
        return SpotQuote(
            metal=_normalize_metal(metal),
            currency=currency_code,
            price_per_gram=Decimal("100.000000"),
            provider_price=provider_price,
            provider_units=f"{currency_code}/troy_oz",
            source=self.provider_name,
            as_of=now,
            fetched_at=now,
            cache_hit=False,
        )


class UnconfiguredMetalsPriceAdapter(MetalsPriceAdapter):
    provider_name = "unconfigured"

    def spot_price(self, metal: str, currency: str = "AUD") -> SpotQuote:
        raise MetalsUnavailable(
            "Live metals pricing is disabled because METALS_PROVIDER is not configured."
        )


def get_metals_adapter() -> MetalsPriceAdapter:
    provider = settings.METALS_PROVIDER.strip().lower()
    if not provider:
        return UnconfiguredMetalsPriceAdapter()
    if provider == "fake":
        return FakeMetalsPriceAdapter()
    return HttpMetalsPriceAdapter()


def _normalize_metal(metal: str) -> str:
    code = str(metal or "").strip().lower()
    if code not in {"gold", "silver", "platinum", "palladium"}:
        raise MetalsUnavailable(f"Unsupported metal: {metal}")
    return code


def _normalize_currency(currency: str) -> str:
    code = str(currency or "").strip().upper()
    if len(code) != 3:
        raise MetalsUnavailable(f"Unsupported currency: {currency}")
    return code


def _decimal(value, field_name: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be a decimal value.") from exc


def _parse_timestamp(value: str) -> datetime:
    text = str(value)
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    parsed = datetime.fromisoformat(text)
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone=datetime_timezone.utc)
    return parsed


def _provider_units(currency: str, unit: str) -> str:
    if unit in {"toz", "troy_oz", "troy_ounce", "troy-ounce"}:
        return f"{currency}/troy_oz"
    if unit in {"g", "gram", "grams"}:
        return f"{currency}/g"
    raise ValueError(f"Unsupported provider unit: {unit}")


def _normalize_price_per_gram(provider_price: Decimal, provider_units: str) -> Decimal:
    if provider_units.endswith("/g"):
        return provider_price.quantize(SPOT_PLACES)
    if provider_units.endswith("/troy_oz"):
        return (provider_price / TROY_OUNCE_GRAMS).quantize(SPOT_PLACES)
    raise ValueError(f"Unsupported provider units: {provider_units}")
