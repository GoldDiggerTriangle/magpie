from __future__ import annotations

import csv
import inspect
from datetime import date, timedelta
from decimal import Decimal
from io import StringIO

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.acquisitions.models import AcquisitionRecord
from apps.catalog.models import ProductCategory
from apps.inventory.models import InventoryItem
from apps.listing.models import ListingDraft
from apps.profit.models import ProfitSetting
from apps.sales.models import SaleRecord


pytestmark = pytest.mark.django_db


@pytest.fixture
def user(django_user_model):
    return django_user_model.objects.create_user(username="sprint20", password="pass")


@pytest.fixture
def api_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def setting():
    return ProfitSetting.objects.create(
        seller_mode=ProfitSetting.SellerMode.FREE_SELLING,
        default_roi_pct=Decimal("30.000"),
    )


@pytest.fixture
def category():
    return ProductCategory.objects.create(
        name="Sprint 20 Stamps",
        slug="sprint-20-stamps",
        sku_prefix="S20",
        profile_key="stamps",
    )


def make_item(
    category,
    *,
    title="Sprint 20 item",
    acquired_on=date(2026, 6, 1),
    acquisition_cost=Decimal("50.00"),
    refurb_cost=Decimal("0.00"),
    inbound_shipping_cost=Decimal("0.00"),
    packaging_cost=Decimal("0.00"),
    status=InventoryItem.Status.CAPTURED,
    quantity_total=1,
):
    acquisition = None
    if acquired_on is not None:
        acquisition = AcquisitionRecord.objects.create(
            source="Sprint 20 fixture",
            acquired_on=acquired_on,
            total_cost=acquisition_cost,
        )
    return InventoryItem.objects.create(
        title=title,
        category=category,
        acquisition=acquisition,
        acquisition_cost=acquisition_cost,
        refurb_cost=refurb_cost,
        inbound_shipping_cost=inbound_shipping_cost,
        est_packaging_cost=packaging_cost,
        quantity_total=quantity_total,
        status=status,
    )


def make_sale(
    item,
    *,
    sale_date=date(2026, 6, 10),
    sale_price=Decimal("100.00"),
    fees=Decimal("0.00"),
    shipping=Decimal("0.00"),
    channel=SaleRecord.Channel.MANUAL,
    seller_mode=ProfitSetting.SellerMode.FREE_SELLING,
    fee_status=SaleRecord.FeeStatus.AUTHORITATIVE,
    listing_draft=None,
):
    return SaleRecord.objects.create(
        item=item,
        sale_date=sale_date,
        sale_price=sale_price,
        quantity=1,
        channel=channel,
        actual_fees_total=fees,
        actual_fee_breakdown={"recorded": str(fees)} if fee_status == SaleRecord.FeeStatus.AUTHORITATIVE else {},
        actual_shipping_cost=shipping,
        fee_status=fee_status,
        listing_draft=listing_draft,
        channel_data={"seller_mode": seller_mode},
    )


def test_per_sale_pnl_uses_actual_recorded_fees_before_schedule_derivation(api_client, setting, category):
    actual_fee_item = make_item(
        category,
        acquired_on=date(2026, 6, 1),
        acquisition_cost=Decimal("50.00"),
        refurb_cost=Decimal("10.00"),
        inbound_shipping_cost=Decimal("5.00"),
        packaging_cost=Decimal("2.00"),
    )
    make_sale(
        actual_fee_item,
        sale_price=Decimal("100.00"),
        fees=Decimal("5.00"),
        shipping=Decimal("4.00"),
        seller_mode=ProfitSetting.SellerMode.PRO_STARTER,
    )
    derived_fee_item = make_item(
        category,
        title="Schedule-derived fee item",
        acquired_on=date(2026, 6, 1),
        acquisition_cost=Decimal("50.00"),
    )
    make_sale(
        derived_fee_item,
        sale_price=Decimal("100.00"),
        fees=Decimal("99.00"),
        fee_status=SaleRecord.FeeStatus.ESTIMATED_OR_UNMAPPED,
        seller_mode=ProfitSetting.SellerMode.PRO_STARTER,
    )

    response = api_client.get("/api/profit/ledger/")

    assert response.status_code == 200, response.data
    by_title = {row["title"]: row for row in response.data["ledger"]}
    actual = by_title["Sprint 20 item"]
    assert actual["fee_provenance"] == "actual_recorded"
    assert actual["fees"] == "5.00"
    assert actual["total_costs"] == "71.00"
    assert actual["realised_profit"] == "24.00"
    assert actual["all_in_roi"] == "33.80"

    derived = by_title["Schedule-derived fee item"]
    assert derived["fee_provenance"] == "schedule_derived"
    assert derived["fees"] == "13.40"
    assert derived["realised_profit"] == "36.60"


def test_negative_profit_missing_date_and_missing_cost_are_honest(api_client, setting, category):
    loss_item = make_item(category, title="Loss item", acquired_on=date(2026, 6, 12), acquisition_cost=Decimal("100.00"))
    make_sale(loss_item, sale_date=date(2026, 6, 10), sale_price=Decimal("50.00"))
    missing_date_item = make_item(category, title="Missing date item", acquired_on=None, acquisition_cost=Decimal("20.00"))
    make_sale(missing_date_item, sale_date=date(2026, 6, 10), sale_price=Decimal("50.00"))
    missing_cost_item = make_item(category, title="Missing cost item", acquired_on=date(2026, 6, 1), acquisition_cost=None)
    make_sale(missing_cost_item, sale_date=date(2026, 6, 10), sale_price=Decimal("50.00"))

    response = api_client.get("/api/profit/ledger/")

    assert response.status_code == 200, response.data
    by_title = {row["title"]: row for row in response.data["ledger"]}
    assert by_title["Loss item"]["days_held"] == 1
    assert by_title["Loss item"]["days_held_basis"] == "recorded_acquisition_guarded_min_1"
    assert by_title["Loss item"]["realised_profit"] == "-50.00"
    assert by_title["Loss item"]["is_loss"] is True
    assert by_title["Missing date item"]["days_held"] is None
    assert by_title["Missing date item"]["velocity_state"] == "unknown_date"
    assert by_title["Missing cost item"]["cost_state"] == "unknown"
    assert by_title["Missing cost item"]["realised_profit"] is None


def test_cash_lock_buckets_stale_threshold_and_unknown_cost_warning(api_client, setting, category):
    today = timezone.localdate()
    unlisted = make_item(category, title="Unlisted stock", acquisition_cost=Decimal("40.00"))
    fresh = make_item(category, title="Fresh listed stock", acquisition_cost=Decimal("50.00"), status=InventoryItem.Status.LISTED)
    stale = make_item(category, title="Stale listed stock", acquisition_cost=Decimal("60.00"), status=InventoryItem.Status.LISTED)
    unknown = make_item(category, title="Unknown cost stock", acquisition_cost=None)
    ListingDraft.objects.create(
        item=fresh,
        status=ListingDraft.Status.PUBLISHED,
        channel_data={"published_at": (today - timedelta(days=10)).isoformat()},
    )
    ListingDraft.objects.create(
        item=stale,
        status=ListingDraft.Status.PUBLISHED,
        channel_data={"published_at": (today - timedelta(days=90)).isoformat()},
    )

    response = api_client.get("/api/profit/ledger/", {"stale_days": "90"})

    assert response.status_code == 200, response.data
    buckets = {bucket["id"]: bucket for bucket in response.data["cash_lock"]["buckets"]}
    assert buckets["unlisted"]["item_count"] == 2
    assert buckets["unlisted"]["unknown_cost_item_count"] == 1
    assert buckets["listed_fresh"]["cash_locked"] == "50.00"
    assert buckets["listed_stale"]["cash_locked"] == "60.00"
    assert buckets["listed_stale"]["items"][0]["nudge"].endswith("reprice or relist?")
    assert "understated" in response.data["cash_lock"]["warning"]
    assert buckets["unlisted"]["items"][0]["hint"]


def test_buy_more_ranking_threshold_and_loss_making_groups(api_client, setting, category):
    positive_category = category
    loss_category = ProductCategory.objects.create(name="Sprint 20 Losses", slug="sprint-20-losses", sku_prefix="L20")
    thin_category = ProductCategory.objects.create(name="Sprint 20 Thin", slug="sprint-20-thin", sku_prefix="T20")
    for index, amount in enumerate(["50.00", "60.00", "70.00"]):
        item = make_item(positive_category, title=f"Positive {index}", acquired_on=date(2026, 6, 1), acquisition_cost=Decimal("10.00"))
        make_sale(item, sale_date=date(2026, 6, 10 + index), sale_price=Decimal(amount), channel=SaleRecord.Channel.EBAY_AU)
    for index in range(3):
        item = make_item(loss_category, title=f"Loss {index}", acquired_on=date(2026, 6, 1), acquisition_cost=Decimal("100.00"))
        make_sale(item, sale_date=date(2026, 6, 10 + index), sale_price=Decimal("20.00"), channel=SaleRecord.Channel.EBAY_AU)
    for index in range(2):
        item = make_item(thin_category, title=f"Thin {index}", acquired_on=date(2026, 6, 1), acquisition_cost=Decimal("10.00"))
        make_sale(item, sale_date=date(2026, 6, 10 + index), sale_price=Decimal("50.00"), channel=SaleRecord.Channel.MANUAL)

    response = api_client.get("/api/profit/ledger/")

    assert response.status_code == 200, response.data
    groups = {(row["category"], row["channel"]): row for row in response.data["buy_more"]["groups"]}
    assert groups[(positive_category.name, SaleRecord.Channel.EBAY_AU)]["status"] == "ranked"
    assert groups[(positive_category.name, SaleRecord.Channel.EBAY_AU)]["recommended"] is True
    assert groups[(loss_category.name, SaleRecord.Channel.EBAY_AU)]["status"] == "loss_making"
    assert groups[(loss_category.name, SaleRecord.Channel.EBAY_AU)]["recommended"] is False
    assert groups[(thin_category.name, SaleRecord.Channel.MANUAL)]["status"] == "insufficient_data"
    assert groups[(thin_category.name, SaleRecord.Channel.MANUAL)]["label"] == "insufficient data (n = 2)"


def test_financial_year_boundary_and_csv_export(api_client, setting, category):
    june_item = make_item(category, title="30 June sale", acquired_on=date(2026, 6, 1), acquisition_cost=Decimal("10.00"))
    july_item = make_item(category, title="1 July sale", acquired_on=date(2026, 6, 1), acquisition_cost=Decimal("10.00"))
    make_sale(june_item, sale_date=date(2026, 6, 30), sale_price=Decimal("40.00"), fees=Decimal("2.00"))
    make_sale(july_item, sale_date=date(2026, 7, 1), sale_price=Decimal("50.00"), fees=Decimal("3.00"))

    response = api_client.get("/api/profit/ledger/", {"fy": "2025-2026"})
    assert response.status_code == 200, response.data
    assert response.data["not_tax_advice_label"] == "Sale records for your accountant - not tax advice."
    assert response.data["financial_years"]["selected"]["start"] == "2025-07-01"
    assert response.data["financial_years"]["selected"]["end"] == "2026-06-30"
    assert response.data["financial_years"]["summary"]["sale_count"] == 1
    assert response.data["financial_years"]["summary"]["revenue"] == "40.00"

    csv_response = api_client.get("/api/profit/ledger.csv", {"fy": "2025-2026"})
    assert csv_response.status_code == 200
    rows = list(csv.DictReader(StringIO(csv_response.content.decode("utf-8"))))
    assert rows[0]["sold_date"] == "2026-06-30"
    assert rows[0]["title"] == "30 June sale"
    assert rows[0]["revenue"] == "40.00"
    assert rows[0]["fee_provenance"] == "actual_recorded"
    assert rows[0]["realised_profit"] == "28.00"
    assert "seller_mode" in rows[0]
    assert "days_held" in rows[0]


def test_profit_api_has_no_predictive_fields_and_no_new_network_calls(api_client, setting, category):
    item = make_item(category, acquisition_cost=Decimal("10.00"))
    make_sale(item, sale_price=Decimal("30.00"))
    response = api_client.get("/api/profit/ledger/")
    assert response.status_code == 200, response.data
    payload = str(response.data).lower()
    forbidden_fields = ["forecast", "prediction", "predicted_value", "ai_price"]
    for token in forbidden_fields:
        assert token not in payload

    import apps.profit.ledger as ledger

    source = inspect.getsource(ledger)
    forbidden_network = ["requests", "httpx", "urlopen", "urllib.request", "ebay_sdk", "openai"]
    for token in forbidden_network:
        assert token not in source
