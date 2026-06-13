from decimal import Decimal
import json

import pytest
from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APIClient

import integrations.metals as metals_module
from integrations.metals import HttpMetalsPriceAdapter
from apps.catalog.models import ProductCategory
from apps.core.backup_ops import DB_SNAPSHOT_NAME
from apps.core.tests.backup_helpers import (
    load_backup_manifest,
    run_encrypted_backup,
    sqlite_count,
)
from apps.inventory.models import InventoryItem
from apps.valuation.models import MetalSpotCache, ValuationReport
from apps.valuation.services import get_spot
from apps.valuation.strategies import (
    karat_to_fineness,
    price_per_troy_ounce_to_price_per_gram,
)


@pytest.fixture
def user(django_user_model):
    return django_user_model.objects.create_user(username="sprint3", password="pass")


@pytest.fixture
def api_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def gold_category():
    return ProductCategory.objects.create(
        name="Gold",
        slug="gold-sprint3",
        sku_prefix="GOLD",
        profile_key="gold",
    )


@pytest.fixture
def gold_item(gold_category):
    return InventoryItem.objects.create(
        title="Gold test parcel",
        category=gold_category,
        attributes={"metal": "gold", "weight_g": "10", "karat": "18"},
    )


class DummyResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def test_karat_and_troy_ounce_helpers():
    assert karat_to_fineness("24") == Decimal("1")
    assert karat_to_fineness("18") == Decimal("0.75")
    assert karat_to_fineness("14") == Decimal("0.5833333333333333333333333333")
    assert karat_to_fineness("9") == Decimal("0.375")
    assert price_per_troy_ounce_to_price_per_gram("3110.347680") == Decimal("100")


def test_http_metals_adapter_parses_metals_dev_without_network(settings, monkeypatch):
    settings.METALS_PROVIDER = "metals.dev"

    def fake_urlopen(request, timeout):
        assert "api.metals.dev/v1/metal/spot" in request.full_url
        assert "metal=gold" in request.full_url
        assert "currency=AUD" in request.full_url
        assert "unit=toz" in request.full_url
        return DummyResponse(
            {
                "status": "success",
                "timestamp": "2026-06-10T00:00:00Z",
                "currency": "AUD",
                "unit": "toz",
                "metal": "gold",
                "rate": {"price": 3110.347680},
            }
        )

    monkeypatch.setattr(metals_module, "urlopen", fake_urlopen)

    quote = HttpMetalsPriceAdapter(api_key="test-key").spot_price("gold", "AUD")

    assert quote.metal == "gold"
    assert quote.currency == "AUD"
    assert quote.provider_units == "AUD/troy_oz"
    assert quote.provider_price == Decimal("3110.34768")
    assert quote.price_per_gram == Decimal("100")
    assert quote.source == "metals.dev"
    assert quote.cache_hit is False


@pytest.mark.django_db
def test_spot_endpoint_uses_db_cache_and_refresh(api_client, settings):
    settings.METALS_PROVIDER = "fake"

    first = api_client.get("/api/metals/spot/", {"metal": "gold", "currency": "AUD"})
    assert first.status_code == 200, first.data
    assert first.data["price_per_gram"] == "100.000000"
    assert first.data["source"] == "fake"
    assert first.data["cache_hit"] is False

    cached = api_client.get("/api/metals/spot/", {"metal": "gold", "currency": "AUD"})
    assert cached.status_code == 200, cached.data
    assert cached.data["cache_hit"] is True

    refreshed = api_client.get(
        "/api/metals/spot/",
        {"metal": "gold", "currency": "AUD", "refresh": "true"},
    )
    assert refreshed.status_code == 200, refreshed.data
    assert refreshed.data["cache_hit"] is False
    assert MetalSpotCache.objects.filter(metal="gold", currency="AUD", provider="fake").count() == 1


@pytest.mark.django_db
def test_get_spot_ttl_cache_and_force_refresh(settings):
    settings.METALS_PROVIDER = "fake"
    settings.METALS_CACHE_TTL_SECONDS = 3600
    now = timezone.now()
    MetalSpotCache.objects.create(
        metal="gold",
        currency="AUD",
        provider="fake",
        price_per_gram=Decimal("88.000000"),
        provider_price=Decimal("2737.105958"),
        provider_units="AUD/troy_oz",
        as_of=now,
        fetched_at=now,
    )

    cached = get_spot("gold", "AUD")
    assert cached.cache_hit is True
    assert cached.price_per_gram == Decimal("88.000000")

    refreshed = get_spot("gold", "AUD", force_refresh=True)
    assert refreshed.cache_hit is False
    assert refreshed.price_per_gram == Decimal("100.000000")


@pytest.mark.django_db
def test_commodity_live_report_snapshots_provenance(api_client, settings, gold_item):
    settings.METALS_PROVIDER = "fake"

    response = api_client.post(
        f"/api/items/{gold_item.id}/valuation-reports/",
        {
            "strategy": "commodity_live",
            "inputs": {
                "metal": "gold",
                "currency": "AUD",
                "weight_g": "10",
                "karat": "18",
                "buy_margin_pct": "10",
            },
        },
        format="json",
    )

    assert response.status_code == 201, response.data
    assert Decimal(response.data["estimate_median"]) == Decimal("750.00")
    assert Decimal(response.data["fast_sale_price"]) == Decimal("675.00")
    inputs = response.data["inputs"]
    assert inputs["metal"] == "gold"
    assert inputs["currency"] == "AUD"
    assert inputs["normalized_price_per_g"] == "100.000000"
    assert inputs["provider_price"] == "3110.347680"
    assert inputs["provider_units"] == "AUD/troy_oz"
    assert inputs["source"] == "fake"
    assert inputs["cache_hit"] is False
    assert inputs["weight_g"] == "10"
    assert inputs["fineness"] == "0.75"
    assert inputs["calculated_intrinsic_value"] == "750.00"
    assert inputs["as_of"]
    assert inputs["fetched_at"]


@pytest.mark.django_db
def test_live_report_missing_inputs_422_and_unconfigured_fallback(
    api_client,
    settings,
    gold_item,
):
    settings.METALS_PROVIDER = ""

    missing_weight = api_client.post(
        f"/api/items/{gold_item.id}/valuation-reports/",
        {
            "strategy": "commodity_live",
            "inputs": {"metal": "gold", "fineness": "0.5"},
        },
        format="json",
    )
    assert missing_weight.status_code == 422
    assert "inputs" in missing_weight.data

    unavailable = api_client.post(
        f"/api/items/{gold_item.id}/valuation-reports/",
        {
            "strategy": "commodity_live",
            "inputs": {"metal": "gold", "weight_g": "5", "fineness": "0.5"},
        },
        format="json",
    )
    assert unavailable.status_code == 503
    assert unavailable.data["needs_manual_spot"] is True
    assert unavailable.data["fallback_strategy"] == "commodity_manual"

    manual = api_client.post(
        f"/api/items/{gold_item.id}/valuation-reports/",
        {
            "strategy": "commodity_manual",
            "inputs": {
                "metal": "gold",
                "weight_g": "5",
                "fineness": "0.5",
                "spot_price_per_g": "100",
            },
        },
        format="json",
    )
    assert manual.status_code == 201, manual.data
    assert Decimal(manual.data["estimate_median"]) == Decimal("250.00")


@pytest.mark.django_db
def test_spot_endpoint_unconfigured_returns_manual_fallback(api_client, settings):
    settings.METALS_PROVIDER = ""

    response = api_client.get("/api/metals/spot/", {"metal": "gold", "currency": "AUD"})

    assert response.status_code == 503
    assert response.data["needs_manual_spot"] is True
    assert response.data["fallback_strategy"] == "commodity_manual"


@pytest.mark.django_db
def test_gold_schema_partial_capture_and_invalid_values(api_client, gold_category):
    partial = api_client.post(
        "/api/items/",
        {
            "title": "Partial gold item",
            "category": str(gold_category.id),
            "condition": "ungraded",
            "location": None,
            "acquisition_cost": None,
            "estimated_value": None,
            "notes": "",
            "attributes": {},
        },
        format="json",
    )
    assert partial.status_code == 201, partial.data
    assert partial.data["attributes"] == {"metal": "gold"}

    invalid = api_client.post(
        "/api/items/",
        {
            "title": "Invalid gold item",
            "category": str(gold_category.id),
            "condition": "ungraded",
            "location": None,
            "acquisition_cost": None,
            "estimated_value": None,
            "notes": "",
            "attributes": {"weight_g": "-1"},
        },
        format="json",
    )
    assert invalid.status_code == 400
    assert "attributes" in invalid.data

    unknown = api_client.post(
        "/api/items/",
        {
            "title": "Unknown gold attribute",
            "category": str(gold_category.id),
            "condition": "ungraded",
            "location": None,
            "acquisition_cost": None,
            "estimated_value": None,
            "notes": "",
            "attributes": {"catalogue_link": "out-of-scope"},
        },
        format="json",
    )
    assert unknown.status_code == 400
    assert "attributes" in unknown.data


@pytest.mark.django_db
def test_live_override_with_reason_still_wins(api_client, settings, gold_item):
    settings.METALS_PROVIDER = "fake"

    response = api_client.post(
        f"/api/items/{gold_item.id}/valuation-reports/",
        {
            "strategy": "commodity_live",
            "is_overridden": True,
            "override_reason": "Human appraiser chose a rounded retail target.",
            "suggested_price": "999.00",
            "inputs": {"metal": "gold", "weight_g": "10", "fineness": "0.5"},
        },
        format="json",
    )

    assert response.status_code == 201, response.data
    assert Decimal(response.data["estimate_median"]) == Decimal("500.00")
    assert Decimal(response.data["suggested_price"]) == Decimal("999.00")
    assert response.data["is_overridden"] is True
    assert response.data["override_reason"]


@pytest.mark.django_db(transaction=True)
def test_backup_json_restore_includes_metal_spot_cache(tmp_path, monkeypatch, gold_item):
    now = timezone.now()
    MetalSpotCache.objects.create(
        metal="gold",
        currency="AUD",
        provider="fake",
        price_per_gram=Decimal("100.000000"),
        provider_price=Decimal("3110.347680"),
        provider_units="AUD/troy_oz",
        as_of=now,
        fetched_at=now,
    )
    ValuationReport.objects.create(
        item=gold_item,
        strategy=ValuationReport.Strategy.COMMODITY_LIVE,
        estimate_median=Decimal("750.00"),
        inputs={
            "metal": "gold",
            "currency": "AUD",
            "normalized_price_per_g": "100.000000",
            "provider_price": "3110.347680",
            "provider_units": "AUD/troy_oz",
            "source": "fake",
            "as_of": now.isoformat(),
            "fetched_at": now.isoformat(),
            "cache_hit": False,
            "weight_g": "10",
            "fineness": "0.75",
            "calculated_intrinsic_value": "750.00",
        },
    )

    _, extract_dir = run_encrypted_backup(tmp_path, monkeypatch)
    manifest = load_backup_manifest(extract_dir)

    assert manifest["row_counts"]["valuation.metalspotcache"] == 1
    restored_db = extract_dir / DB_SNAPSHOT_NAME
    assert sqlite_count(restored_db, "valuation_metalspotcache") == 1
    assert sqlite_count(restored_db, "valuation_valuationreport") == 1
