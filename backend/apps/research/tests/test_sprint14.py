from datetime import date, timedelta
from decimal import Decimal
from urllib.parse import parse_qs, urlparse

import pytest
from django.db import connection
from django.utils import timezone
from rest_framework.test import APIClient

from apps.catalog.models import ProductCategory
from apps.core.backup_ops import DB_SNAPSHOT_NAME
from apps.core.tests.backup_helpers import (
    load_backup_manifest,
    run_encrypted_backup,
    sqlite_count,
)
from apps.inventory.models import InventoryItem
from apps.research.models import Comparable
from apps.sales.models import SaleRecord
from apps.sales.services import create_sale_record


@pytest.fixture
def user(django_user_model):
    return django_user_model.objects.create_user(username="pricing-evidence", password="pass")


@pytest.fixture
def api_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def coin_category():
    return ProductCategory.objects.create(
        name="Coins",
        slug="sprint-14-coins",
        sku_prefix="S14",
        profile_key="coins",
    )


def make_coin(category, *, title="1937 Australian Crown", year=1937, denomination="Crown"):
    return InventoryItem.objects.create(
        title=title,
        category=category,
        condition=InventoryItem.Condition.GOOD,
        quantity_total=5,
        acquisition_cost=Decimal("100.00"),
        estimated_value=Decimal("60.00"),
        attributes={
            "country": "Australia",
            "year": year,
            "denomination": denomination,
            "grade": "VF",
        },
    )


def sale(item, *, sale_date=date(2026, 6, 1), quantity=1, price="60.00", channel=SaleRecord.Channel.MANUAL):
    return create_sale_record(
        data={
            "item": item,
            "sale_date": sale_date,
            "quantity": quantity,
            "sale_price": Decimal(price),
            "channel": channel,
            "actual_fees_total": Decimal("0.00"),
            "actual_shipping_cost": Decimal("0.00"),
        }
    )


@pytest.mark.django_db
def test_pricing_evidence_ranks_exact_own_sales_before_similar(api_client, coin_category):
    target = make_coin(coin_category)
    similar = make_coin(coin_category, title="1937 Crown second example")
    exact_sale = sale(target, sale_date=date(2026, 6, 10), price="70.00")
    similar_sale = sale(similar, sale_date=date(2026, 6, 11), price="55.00")

    response = api_client.get(f"/api/items/{target.id}/pricing-evidence/")

    assert response.status_code == 200, response.data
    own_sales = response.data["own_sales"]
    assert own_sales[0]["id"] == f"sale:{exact_sale.id}"
    assert own_sales[0]["match_scope"] == "exact"
    assert own_sales[0]["own_sale"] is True
    assert own_sales[1]["id"] == f"sale:{similar_sale.id}"
    assert own_sales[1]["match_scope"] == "similar"
    assert "same category" in own_sales[1]["match_reason"]
    assert "same denomination" in own_sales[1]["match_reason"]
    assert "same year" in own_sales[1]["match_reason"]


@pytest.mark.django_db
def test_source_registry_builds_view_only_urls_without_fetching(api_client, coin_category):
    item = make_coin(coin_category)

    response = api_client.get(f"/api/items/{item.id}/pricing-evidence/")

    assert response.status_code == 200, response.data
    links = {link["id"]: link for link in response.data["source_links"]}
    assert {"ebay_sold", "facebook_marketplace", "invaluable", "worthpoint", "numista"} <= set(links)
    ebay = links["ebay_sold"]
    params = parse_qs(urlparse(ebay["url"]).query)
    assert ebay["primary"] is True
    assert ebay["url"].startswith("https://www.ebay.com.au/sch/i.html?")
    assert params["LH_Sold"] == ["1"]
    assert params["LH_Complete"] == ["1"]
    assert links["facebook_marketplace"]["url"].startswith("https://www.facebook.com/marketplace/search/")

    import apps.research.pricing_sources as pricing_sources

    source = pricing_sources.__loader__.get_source(pricing_sources.__name__)
    assert "requests" not in source
    assert "httpx" not in source
    assert "urlopen" not in source


@pytest.mark.django_db
def test_capture_to_grid_creates_source_tagged_comparable(api_client, coin_category):
    item = make_coin(coin_category)

    created = api_client.post(
        "/api/comparables/",
        {
            "item": str(item.id),
            "kind": Comparable.Kind.SOLD,
            "source": "WorthPoint manual capture",
            "source_tag": "price guide",
            "title": "1937 Australian Crown VF sold result",
            "price": "65.00",
            "shipping": "5.00",
            "currency": "AUD",
            "condition": InventoryItem.Condition.GOOD,
            "grade": "VF",
            "sale_format": Comparable.SaleFormat.DEALER,
            "match_scope": Comparable.MatchScope.SIMILAR,
            "match_reason": "same category; same denomination; same year",
            "url": "https://www.worthpoint.com/inventory/search?query=1937%20crown",
            "observed_on": "2026-06-14",
            "notes": "User verified this sold-result page manually.",
        },
        format="json",
    )

    assert created.status_code == 201, created.data
    assert created.data["source_tag"] == "price_guide"
    assert created.data["sale_format"] == "dealer"
    assert created.data["match_scope"] == "similar"

    evidence = api_client.get(f"/api/items/{item.id}/pricing-evidence/")
    assert evidence.status_code == 200, evidence.data
    source_cells = {cell["key"]: cell for cell in evidence.data["grids"]["source"]}
    assert source_cells["price_guide"]["count"] == 1
    assert source_cells["price_guide"]["median"] == "65.00"
    assert evidence.data["comparables"][0]["source_tag"] == "price_guide"


@pytest.mark.django_db
def test_pricing_grids_aggregate_low_median_high_by_required_cuts(api_client, coin_category):
    item = make_coin(coin_category)
    sale(item, sale_date=timezone.localdate() - timedelta(days=30), quantity=2, price="100.00")
    Comparable.objects.create(
        item=item,
        kind=Comparable.Kind.SOLD,
        source="eBay manual capture",
        source_tag="ebay_sold",
        title="Exact Crown sold",
        price=Decimal("60.00"),
        condition=InventoryItem.Condition.GOOD,
        grade="VF",
        sale_format=Comparable.SaleFormat.AUCTION,
        match_scope=Comparable.MatchScope.EXACT,
        match_reason="same inventory item",
        observed_on=timezone.localdate() - timedelta(days=120),
    )
    Comparable.objects.create(
        item=item,
        kind=Comparable.Kind.SOLD,
        source="Auction archive",
        source_tag="auction_archive",
        title="Similar Crown sold",
        price=Decimal("90.00"),
        condition=InventoryItem.Condition.GOOD,
        grade="VF",
        sale_format=Comparable.SaleFormat.AUCTION,
        match_scope=Comparable.MatchScope.SIMILAR,
        match_reason="same category; same denomination; same year",
        observed_on=timezone.localdate() - timedelta(days=500),
    )

    response = api_client.get(f"/api/items/{item.id}/pricing-evidence/")

    assert response.status_code == 200, response.data
    assert response.data["summary"]["priced_count"] == 3
    condition_cells = {cell["key"]: cell for cell in response.data["grids"]["condition_grade"]}
    assert condition_cells["good / VF"]["low"] == "50.00"
    assert condition_cells["good / VF"]["median"] == "60.00"
    assert condition_cells["good / VF"]["high"] == "90.00"
    assert condition_cells["good / VF"]["count"] == 3
    format_cells = {cell["key"]: cell for cell in response.data["grids"]["sale_format"]}
    assert format_cells["auction"]["count"] == 2
    source_cells = {cell["key"]: cell for cell in response.data["grids"]["source"]}
    assert source_cells["own_sale"]["own_sale_count"] == 1
    recency_keys = {cell["key"] for cell in response.data["grids"]["recency"]}
    assert {"0-90 days", "91-365 days", "older than 365 days"} <= recency_keys


@pytest.mark.django_db
def test_pricing_evidence_empty_and_thin_states(api_client, coin_category):
    item = make_coin(coin_category)

    empty = api_client.get(f"/api/items/{item.id}/pricing-evidence/")

    assert empty.status_code == 200, empty.data
    assert empty.data["summary"]["empty"] is True
    assert empty.data["summary"]["thin"] is True
    assert empty.data["empty_state"]["title"] == "No pricing evidence yet"

    Comparable.objects.create(
        item=item,
        kind=Comparable.Kind.SOLD,
        source="Manual comp",
        source_tag="manual",
        price=Decimal("52.00"),
        match_scope=Comparable.MatchScope.EXACT,
        match_reason="same inventory item",
    )
    thin = api_client.get(f"/api/items/{item.id}/pricing-evidence/")
    assert thin.data["summary"]["empty"] is False
    assert thin.data["summary"]["thin"] is True
    assert thin.data["empty_state"]["title"] == "Thin pricing evidence"


@pytest.mark.django_db(transaction=True)
def test_backup_restore_includes_comparable_pricing_fields(tmp_path, monkeypatch, coin_category):
    if connection.vendor != "sqlite":
        pytest.skip("Sprint 8 backup command is SQLite-only.")

    item = make_coin(coin_category)
    Comparable.objects.create(
        item=item,
        kind=Comparable.Kind.SOLD,
        source="WorthPoint manual capture",
        source_tag="price_guide",
        price=Decimal("75.00"),
        grade="VF",
        sale_format=Comparable.SaleFormat.DEALER,
        match_scope=Comparable.MatchScope.SIMILAR,
        match_reason="same category; same denomination; same year",
    )

    _, extract_dir = run_encrypted_backup(tmp_path, monkeypatch)
    manifest = load_backup_manifest(extract_dir)
    assert manifest["row_counts"]["research.comparable"] == 1
    assert sqlite_count(extract_dir / DB_SNAPSHOT_NAME, "research_comparable") == 1
