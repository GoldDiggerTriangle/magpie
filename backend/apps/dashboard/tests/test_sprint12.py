from datetime import date, timedelta
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.acquisitions.models import AcquisitionRecord
from apps.catalog.models import ProductCategory
from apps.dashboard.models import DEFAULT_KPI_TILES, DashboardPreference
from apps.ebay.models import EbayOrderStaging
from apps.inventory.models import InventoryItem
from apps.sales.models import SaleRecord
from apps.sales.services import create_sale_record
from apps.valuation.models import FeeSchedule, ValuationReport


@pytest.fixture
def user(django_user_model):
    return django_user_model.objects.create_user(username="dashboard", password="pass")


@pytest.fixture
def api_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def fee_schedule():
    return FeeSchedule.objects.create(
        name="Dashboard fees",
        effective_from=date(2026, 1, 1),
        final_value_pct=Decimal("10.000"),
        per_order_fee=Decimal("0.30"),
        promoted_pct=Decimal("0.000"),
        gst_pct=Decimal("10.000"),
    )


@pytest.fixture
def dashboard_fixture(fee_schedule):
    category = ProductCategory.objects.create(
        name="Stamps",
        slug="dashboard-stamps",
        sku_prefix="STM",
    )
    acquisition = AcquisitionRecord.objects.create(
        source="Estate lot",
        acquired_on=date(2026, 1, 10),
    )
    sold_item = InventoryItem.objects.create(
        title="Stamp lot",
        category=category,
        acquisition=acquisition,
        quantity_total=10,
        acquisition_cost=Decimal("100.00"),
        estimated_value=Decimal("200.00"),
        status=InventoryItem.Status.READY_TO_LIST,
    )
    ValuationReport.objects.create(
        item=sold_item,
        strategy=ValuationReport.Strategy.COMP_BASED,
        is_current=True,
        suggested_price=Decimal("75.00"),
        fee_schedule=fee_schedule,
    )
    known_sale = create_sale_record(
        data={
            "item": sold_item,
            "sale_date": date(2026, 6, 14),
            "quantity": 2,
            "sale_price": Decimal("80.00"),
            "channel": SaleRecord.Channel.MANUAL,
            "actual_fees_total": Decimal("8.00"),
            "actual_shipping_cost": Decimal("2.00"),
        }
    )
    external_sale = create_sale_record(
        data={
            "item": None,
            "is_external": True,
            "cost_basis_unknown": True,
            "sale_date": date(2026, 6, 15),
            "quantity": 1,
            "sale_price": Decimal("50.00"),
            "channel": SaleRecord.Channel.EBAY_AU,
            "actual_fees_total": Decimal("5.00"),
            "actual_shipping_cost": Decimal("0.00"),
        }
    )
    available_item = InventoryItem.objects.create(
        title="Gold ring",
        category=category,
        acquisition=AcquisitionRecord.objects.create(
            source="Counter buy",
            acquired_on=date.today() - timedelta(days=120),
        ),
        quantity_total=1,
        acquisition_cost=Decimal("100.00"),
        estimated_value=Decimal("300.00"),
        status=InventoryItem.Status.READY_TO_LIST,
    )
    ValuationReport.objects.create(
        item=available_item,
        strategy=ValuationReport.Strategy.COMP_BASED,
        is_current=True,
        suggested_price=Decimal("330.00"),
        fee_schedule=fee_schedule,
    )
    EbayOrderStaging.objects.create(
        ebay_order_id="ORDER-DASH",
        ebay_line_item_id="LINE-DASH",
        sku="UNKNOWN",
        quantity=1,
        line_price=Decimal("25.00"),
        sale_date=date(2026, 6, 14),
    )
    return {
        "category": category,
        "sold_item": sold_item,
        "known_sale": known_sale,
        "external_sale": external_sale,
        "available_item": available_item,
    }


@pytest.mark.django_db
def test_analytics_summary_uses_honest_profit_rule(api_client, dashboard_fixture):
    response = api_client.get("/api/analytics/summary/?range=all")

    assert response.status_code == 200
    tiles = response.data["tiles"]
    assert tiles["gross_revenue"]["value"] == "130.00"
    assert tiles["net_proceeds"]["value"] == "115.00"
    assert tiles["realised_profit"]["value"] == "50.00"
    assert tiles["realised_profit"]["excluded_count"] == 1
    assert tiles["avg_realised_margin"]["value"] == "62.50"
    assert tiles["items_sold"]["value"] == "3"
    assert tiles["sell_through"]["value"] == "18.18"
    assert tiles["unresolved_ebay_staging_count"]["value"] == "1"
    assert response.data["action_counts"]["cost_basis_unknown_sales"] == 1


@pytest.mark.django_db
def test_average_time_to_sale_ignores_impossible_negative_intervals(
    api_client,
    dashboard_fixture,
):
    category = dashboard_fixture["category"]
    future_acquisition = AcquisitionRecord.objects.create(
        source="Late import",
        acquired_on=date(2026, 7, 1),
    )
    imported_item = InventoryItem.objects.create(
        title="Imported sold item",
        category=category,
        acquisition=future_acquisition,
        quantity_total=1,
        acquisition_cost=Decimal("10.00"),
        estimated_value=Decimal("20.00"),
    )
    create_sale_record(
        data={
            "item": imported_item,
            "sale_date": date(2026, 6, 1),
            "quantity": 1,
            "sale_price": Decimal("20.00"),
            "channel": SaleRecord.Channel.MANUAL,
            "actual_fees_total": Decimal("2.00"),
            "actual_shipping_cost": Decimal("0.00"),
        }
    )

    response = api_client.get("/api/analytics/summary/?range=all")

    assert response.status_code == 200
    assert response.data["tiles"]["avg_time_to_sale"]["value"] == "155"


@pytest.mark.django_db
def test_analytics_sections_return_live_dashboard_payloads(api_client, dashboard_fixture):
    category = dashboard_fixture["category"]

    pnl = api_client.get("/api/analytics/pnl/?range=all")
    assert pnl.status_code == 200
    assert pnl.data["series"][0]["realised_profit"] == "50.00"
    assert pnl.data["series"][0]["net_proceeds"] == "115.00"
    assert pnl.data["small_sample"] is True

    by_category = api_client.get(f"/api/analytics/by-category/?range=all&category={category.id}")
    assert by_category.status_code == 200
    assert by_category.data["categories"][0]["category"] == "Stamps"
    assert by_category.data["categories"][0]["realised_profit"] == "50.00"

    estimate = api_client.get("/api/analytics/estimate-vs-actual/?range=all")
    assert estimate.status_code == 200
    assert estimate.data["accuracy"]["sample_size"] == 1
    assert estimate.data["accuracy"]["small_sample"] is True
    assert estimate.data["points"][0]["estimated"] == "75.00"
    assert estimate.data["points"][0]["actual"] == "80.00"
    assert estimate.data["fees"]["sample_size"] == 1

    aging = api_client.get("/api/analytics/aging/?range=all")
    assert aging.status_code == 200
    assert sum(bucket["count"] for bucket in aging.data["buckets"]) == 2

    opportunities = api_client.get("/api/analytics/listing-opportunities/?range=all")
    assert opportunities.status_code == 200
    assert opportunities.data["items"][0]["sku"] == dashboard_fixture["available_item"].sku
    assert opportunities.data["items"][0]["estimated_value"] == "330.00"


@pytest.mark.django_db
def test_dashboard_preferences_default_sanitize_and_persist(api_client):
    response = api_client.get("/api/dashboard/preferences/")

    assert response.status_code == 200
    assert response.data["kpi_tiles"] == DEFAULT_KPI_TILES
    assert DashboardPreference.objects.count() == 0

    save = api_client.put(
        "/api/dashboard/preferences/",
        {
            "kpi_tiles": [
                "net_proceeds",
                "unknown_tile",
                "items_sold",
                "items_sold",
                "gross_revenue",
                "sell_through",
                "avg_realised_margin",
                "aged_inventory_count",
            ]
        },
        format="json",
    )

    assert save.status_code == 200, save.data
    assert save.data["kpi_tiles"] == [
        "net_proceeds",
        "items_sold",
        "gross_revenue",
        "sell_through",
        "avg_realised_margin",
    ]
    assert DashboardPreference.objects.count() == 1

    reload_response = api_client.get("/api/dashboard/preferences/")
    assert reload_response.data["kpi_tiles"] == save.data["kpi_tiles"]

    too_few = api_client.put(
        "/api/dashboard/preferences/",
        {"kpi_tiles": ["unknown_tile", "items_sold"]},
        format="json",
    )
    assert too_few.status_code == 400
    assert "Choose at least 3" in str(too_few.data["kpi_tiles"][0])
