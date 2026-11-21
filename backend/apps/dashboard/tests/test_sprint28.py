from datetime import date, datetime, timedelta, timezone as dt_timezone
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.dashboard.analytics import parse_filters
from apps.dashboard.models import DEFAULT_KPI_TILES, KPI_TILE_CATALOG, DashboardPreference
from apps.inventory.models import InventoryItem
from apps.listing.models import ChannelListing, ListingDraft
from apps.sales.models import SaleRecord
from apps.sales.services import create_sale_record

pytestmark = pytest.mark.django_db


@pytest.fixture
def api(django_user_model):
    client = APIClient()
    client.force_authenticate(django_user_model.objects.create_user(username="sprint28"))
    return client


@pytest.fixture(autouse=True)
def clock(monkeypatch):
    monkeypatch.setattr("django.utils.timezone.now", lambda: datetime(2026, 11, 21, 1, tzinfo=dt_timezone.utc))


def item(**kwargs):
    return InventoryItem.objects.create(title="Synthetic stock", quantity_total=5, acquisition_cost=Decimal("5.00"), **kwargs)


def sale(stock=None, **kwargs):
    return create_sale_record(data={"item": stock, "sale_date": date(2026, 11, 20), "quantity": 1,
                                   "sale_price": Decimal("1.34"), "channel": "manual", "actual_fees_total": Decimal("0.00"), **kwargs})


def summary(api):
    response = api.get("/api/analytics/summary/", {"range": "this_month"})
    assert response.status_code == 200
    return response.data


def test_registry_and_new_defaults_only_without_saved_preference(api):
    assert len(KPI_TILE_CATALOG) == 14
    assert DEFAULT_KPI_TILES == ["realised_profit", "items_sold", "stock_on_hand", "ebay_listings"]
    assert api.get("/api/dashboard/preferences/").data["kpi_tiles"] == DEFAULT_KPI_TILES
    assert DashboardPreference.objects.count() == 0
    saved = DashboardPreference.objects.create(kpi_tiles=["gross_revenue", "net_proceeds", "items_sold"])
    before = DashboardPreference.objects.values().get(pk=saved.pk)
    assert api.get("/api/dashboard/preferences/").data["kpi_tiles"] == saved.kpi_tiles
    assert DashboardPreference.objects.values().get(pk=saved.pk) == before


def test_multi_unit_cents_and_ledger_parity(api):
    stock = item()
    sale(stock, quantity=3, sale_price=Decimal("3.34"))
    data = summary(api)
    ledger = api.get("/api/profit/ledger/", {"range": "this_month"}).data
    assert data["tiles"]["items_sold"]["value"] == "3"
    assert data["tiles"]["items_sold"]["label"] == "Units sold this month"
    assert data["tiles"]["realised_profit"]["label"] == "Profit this month"
    assert data["tiles"]["realised_profit"]["value"] == ledger["summary"]["realised_profit"] == "0.34"
    assert data["tiles"]["realised_profit"]["state"] == "known"


def test_scrap_loss_without_sales_matches_ledger(api):
    InventoryItem.objects.create(title="Scrap", quantity_total=3, acquisition_cost=Decimal("12.45"), disposition="scrapped", scrapped_at=date(2026, 11, 20))
    data = summary(api)
    ledger = api.get("/api/profit/ledger/", {"range": "this_month"}).data
    assert data["tiles"]["realised_profit"]["value"] == ledger["summary"]["realised_profit"] == "-12.45"
    assert data["tiles"]["realised_profit"]["state"] == "known"
    assert data["tiles"]["items_sold"]["value"] == "0"
    assert "No sales this month" in data["tiles"]["realised_profit"]["secondary"]


def test_no_sales_unknown_and_real_zero_are_distinct(api):
    assert summary(api)["tiles"]["realised_profit"]["state"] == "no_sales"
    sale(is_external=True, cost_basis_unknown=True)
    unknown = summary(api)["tiles"]["realised_profit"]
    assert unknown["state"] == "unknown" and unknown["value"] is None and unknown["excluded_count"] == 1
    sale(item(), sale_price=Decimal("1.00"))
    zero = summary(api)["tiles"]["realised_profit"]
    assert zero["state"] == "known" and zero["value"] == "0.00" and zero["excluded_count"] == 1


def test_month_uses_sydney_boundary_and_does_not_filter_fy_export(api, monkeypatch):
    monkeypatch.setattr("django.utils.timezone.now", lambda: datetime(2026, 11, 30, 13, 30, tzinfo=dt_timezone.utc))
    stock = item()
    sale(stock, sale_date=date(2026, 11, 30))
    sale(stock, sale_date=date(2026, 12, 1))
    assert parse_filters({"range": "this_month"}).start == date(2026, 12, 1)
    data = summary(api)
    ledger = api.get("/api/profit/ledger/", {"range": "this_month", "fy": "2026-2027"}).data
    assert data["tiles"]["items_sold"]["value"] == "1"
    assert data["tiles"]["realised_profit"]["value"] == ledger["summary"]["realised_profit"] == "0.34"
    assert ledger["financial_years"]["summary"]["sale_count"] == 2
    assert ledger["period"]["start"] == "2026-12-01"


def test_stock_counts_known_unknown_and_saleable_remaining(api):
    stock = item(refurb_cost=Decimal("5.00"))
    sale(stock, quantity=2)
    InventoryItem.objects.create(title="Unknown", quantity_total=4)
    item(disposition="scrapped", scrapped_at=date(2026, 11, 20))
    item(status="archived")
    data = summary(api)["tiles"]["stock_on_hand"]
    assert data["value"] == "7"
    assert "3 known-cost units: $6.00" in data["secondary"]
    assert "4 units with unknown cost" in data["secondary"]


def test_ebay_local_active_only_and_unrecorded_allocation_is_not_alert(api):
    stock = item()
    ChannelListing.objects.create(item=stock, channel="ebay")
    ChannelListing.objects.create(item=item(), channel="ebay", ended_at=datetime(2026, 11, 20, tzinfo=dt_timezone.utc))
    ChannelListing.objects.create(item=item(), channel="facebook")
    data = summary(api)
    assert data["tiles"]["ebay_listings"]["value"] == "1"
    assert "Marked active in Magpie" in data["tiles"]["ebay_listings"]["secondary"]
    assert not any(row["id"] == "allocation" for row in data["alerts"])


def test_urgent_unknown_and_stale_only_route_to_existing_queue(api):
    stock = item()
    ListingDraft.objects.create(item=stock, status="publish_unknown")
    old = item()
    ListingDraft.objects.create(item=old, status="publishing", publish_started_at=datetime(2026, 11, 21, 0, tzinfo=dt_timezone.utc))
    ListingDraft.objects.create(item=item(), status="publishing", publish_started_at=datetime(2026, 11, 21, 0, 59, tzinfo=dt_timezone.utc))
    alerts = summary(api)["alerts"]
    assert next(row for row in alerts if row["id"] == "publish") == {"id": "publish", "count": 2, "label": "Publish results need checking", "href": "/ebay#publish-results"}


def test_intentional_smaller_allocation_is_not_an_alert_but_real_urgent_is(api, monkeypatch):
    stock = item()
    ChannelListing.objects.create(item=stock, channel="ebay")
    monkeypatch.setattr("apps.ebay.quantity.item_quantity_state", lambda *args: {"urgent": False, "allocated": 1, "remaining": 5})
    assert not any(row["id"] == "allocation" for row in summary(api)["alerts"])
    monkeypatch.setattr("apps.ebay.quantity.item_quantity_state", lambda *args: {"urgent": True, "state": "update_required"})
    assert next(row for row in summary(api)["alerts"] if row["id"] == "allocation")["href"] == "/ebay#live-listings"


def test_fee_snapshot_and_external_filter_remain_honest(api):
    stock = item()
    sale(stock)
    sale(is_external=True, cost_basis_unknown=True, sale_price=Decimal("8.00"))
    before = summary(api)["tiles"]["realised_profit"]["value"]
    stock.acquisition_cost = Decimal("100.00")
    stock.save()
    assert summary(api)["tiles"]["realised_profit"]["value"] == before == "0.34"
    response = api.get("/api/profit/ledger/", {"range": "this_month", "channel": "external"})
    assert response.data["summary"]["sale_count"] == 1
    assert response.data["summary"]["known_profit_sale_count"] == 0


def test_summary_get_does_not_save_owned_records(api):
    stock = item()
    sale(stock)
    models = [InventoryItem, SaleRecord, DashboardPreference, ListingDraft, ChannelListing]
    before = {model: list(model.objects.order_by("pk").values()) for model in models}
    summary(api)
    assert {model: list(model.objects.order_by("pk").values()) for model in models} == before
