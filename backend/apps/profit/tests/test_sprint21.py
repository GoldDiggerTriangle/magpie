from __future__ import annotations

import csv
import inspect
from datetime import date
from decimal import Decimal
from io import StringIO

import pytest
from rest_framework.test import APIClient

from apps.acquisitions.models import AcquisitionRecord
from apps.catalog.models import ProductCategory
from apps.inventory.models import InventoryItem
from apps.profit import ledger
from apps.profit.lots import allocate_equal, allocate_manual, allocate_proportional, lot_summary, mark_member_scrapped
from apps.profit.models import Lot, ProfitSetting, Source
from apps.sales.models import SaleRecord
from apps.sales.services import create_sale_record


pytestmark = pytest.mark.django_db


@pytest.fixture
def user(django_user_model):
    return django_user_model.objects.create_user(username="sprint21", password="pass")


@pytest.fixture
def api_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def setting():
    return ProfitSetting.objects.create(seller_mode=ProfitSetting.SellerMode.FREE_SELLING)


@pytest.fixture
def category():
    return ProductCategory.objects.create(name="Sprint 21 Stamps", slug="sprint-21-stamps", sku_prefix="S21")


def make_source(name="Estate house", type=Source.Type.ESTATE):
    return Source.objects.create(name=name, type=type)


def make_lot(source=None, *, label="Estate box", total_cost=Decimal("100.00"), purchase_date=date(2026, 6, 1)):
    return Lot.objects.create(label=label, total_cost=total_cost, purchase_date=purchase_date, source=source)


def make_item(category, *, lot=None, source=None, title="Lot member", cost=None, estimate=None, acquired_on=None):
    acquisition = None
    if acquired_on is not None:
        acquisition = AcquisitionRecord.objects.create(source="Sprint 21 fixture", acquired_on=acquired_on, total_cost=cost or Decimal("0.00"))
    return InventoryItem.objects.create(
        title=title,
        category=category,
        lot=lot,
        source=source,
        acquisition=acquisition,
        acquisition_cost=cost,
        estimated_value=estimate,
        quantity_total=1,
    )


def make_sale(item, *, sale_date=date(2026, 6, 10), price=Decimal("100.00"), fees=Decimal("0.00"), channel=SaleRecord.Channel.MANUAL):
    return SaleRecord.objects.create(
        item=item,
        sale_date=sale_date,
        sale_price=price,
        quantity=1,
        actual_fees_total=fees,
        actual_fee_breakdown={"recorded": str(fees)},
        channel=channel,
        fee_status=SaleRecord.FeeStatus.AUTHORITATIVE,
    )


def test_allocation_helpers_round_to_cent_and_warn_on_overallocation(category):
    lot = make_lot(total_cost=Decimal("100.00"))
    a = make_item(category, lot=lot, title="A")
    b = make_item(category, lot=lot, title="B")
    c = make_item(category, lot=lot, title="C")

    summary = allocate_equal(lot)

    values = {row["title"]: row["acquisition_cost"] for row in summary["members"]}
    assert values == {"A": "33.33", "B": "33.33", "C": "33.34"}
    assert summary["tally_label"] == "allocated $100.00 of $100.00 · remainder $0.00"

    manual = allocate_manual(
        lot,
        [
            {"item": a.id, "amount": Decimal("50.00")},
            {"item": b.id, "amount": Decimal("50.00")},
            {"item": c.id, "amount": Decimal("10.00")},
        ],
    )
    assert manual["allocated"] == "110.00"
    assert manual["unallocated"] == "-10.00"
    assert manual["is_over_allocated"] is True
    assert "Over-allocated" in manual["warning"]


def test_proportional_helper_requires_estimates_and_puts_residue_on_last_member(category):
    lot = make_lot(total_cost=Decimal("10.00"))
    make_item(category, lot=lot, title="No estimate")

    with pytest.raises(Exception):
        allocate_proportional(lot)

    lot.items.all().delete()
    make_item(category, lot=lot, title="A", estimate=Decimal("1.00"))
    make_item(category, lot=lot, title="B", estimate=Decimal("1.00"))
    make_item(category, lot=lot, title="C", estimate=Decimal("1.00"))

    summary = allocate_proportional(lot)

    assert [row["acquisition_cost"] for row in summary["members"]] == ["3.33", "3.33", "3.34"]
    assert summary["unallocated"] == "0.00"


def test_sold_lock_keeps_historical_profit_and_redistributes_only_unlocked(setting, category):
    lot = make_lot(total_cost=Decimal("90.00"))
    sold = make_item(category, lot=lot, title="Sold member", cost=Decimal("10.00"))
    open_a = make_item(category, lot=lot, title="Open A")
    open_b = make_item(category, lot=lot, title="Open B")
    make_sale(sold, price=Decimal("50.00"))

    before = api_profit_for_title("Sold member")
    summary = allocate_equal(lot)
    sold.refresh_from_db()
    open_a.refresh_from_db()
    open_b.refresh_from_db()
    after = api_profit_for_title("Sold member")

    assert sold.acquisition_cost == Decimal("10.00")
    assert open_a.acquisition_cost == Decimal("40.00")
    assert open_b.acquisition_cost == Decimal("40.00")
    assert before == "40.00"
    assert after == "40.00"
    assert {row["title"]: row["locked"] for row in summary["members"]}["Sold member"] is True


def test_scrapped_lock_creates_ledger_loss_and_fy_export(setting, api_client, category):
    lot = make_lot(total_cost=Decimal("20.00"), purchase_date=date(2026, 6, 1))
    junk = make_item(category, lot=lot, title="Junk member", cost=Decimal("20.00"))

    mark_member_scrapped(junk, scrapped_at=date(2026, 6, 30))
    locked = allocate_manual(lot, [{"item": junk.id, "amount": Decimal("99.00")}])
    junk.refresh_from_db()

    assert junk.acquisition_cost == Decimal("20.00")
    assert locked["members"][0]["state"] == "scrapped"
    assert locked["members"][0]["locked"] is True

    response = api_client.get("/api/profit/ledger/", {"fy": "2025-2026"})
    assert response.status_code == 200, response.data
    row = next(row for row in response.data["ledger"] if row["title"] == "Junk member")
    assert row["provenance"] == "scrapped"
    assert row["revenue"] == "0.00"
    assert row["realised_profit"] == "-20.00"
    assert row["is_loss"] is True

    csv_response = api_client.get("/api/profit/ledger.csv", {"fy": "2025-2026"})
    rows = list(csv.DictReader(StringIO(csv_response.content.decode("utf-8"))))
    assert any(
        row["title"] == "Junk member"
        and row["provenance"] == "scrapped"
        and row["realised_profit"] == "-20.00"
        for row in rows
    )

    with pytest.raises(Exception, match="Scrapped items are locked"):
        create_sale_record(
            data={
                "item": junk,
                "sale_date": date(2026, 7, 1),
                "quantity": 1,
                "sale_price": Decimal("1.00"),
                "channel": SaleRecord.Channel.MANUAL,
            }
        )


def test_lot_pnl_handles_sold_unsold_and_scrapped_mix(setting, category):
    lot = make_lot(total_cost=Decimal("100.00"))
    sold = make_item(category, lot=lot, title="Sold", cost=Decimal("30.00"))
    scrapped = make_item(category, lot=lot, title="Scrap", cost=Decimal("20.00"))
    make_item(category, lot=lot, title="Unsold", cost=Decimal("40.00"))
    make_sale(sold, price=Decimal("50.00"))
    mark_member_scrapped(scrapped, scrapped_at=date(2026, 6, 20))

    pnl = lot_summary(lot)["pnl"]

    assert pnl["realised_revenue"] == "50.00"
    assert pnl["realised_profit"] == "0.00"
    assert pnl["remaining_cost_basis"] == "40.00"
    assert pnl["recovered_label"] == "recovered $50.00 of $100.00"
    assert pnl["is_part_allocated"] is True


def test_source_inheritance_ledger_aggregate_and_source_ranking(setting, api_client, category):
    estate = make_source("Estate A", Source.Type.ESTATE)
    auction = make_source("Auction B", Source.Type.AUCTION)
    lot = make_lot(source=estate)
    inherited = make_item(category, lot=lot, title="Inherited source", cost=Decimal("10.00"))
    make_sale(inherited, price=Decimal("50.00"), channel=SaleRecord.Channel.EBAY_AU)

    for index in range(2):
        item = make_item(category, source=estate, title=f"Estate win {index}", cost=Decimal("10.00"), acquired_on=date(2026, 6, 1))
        make_sale(item, sale_date=date(2026, 6, 11 + index), price=Decimal("50.00"), channel=SaleRecord.Channel.EBAY_AU)
    for index in range(3):
        item = make_item(category, source=auction, title=f"Auction loss {index}", cost=Decimal("100.00"), acquired_on=date(2026, 6, 1))
        make_sale(item, sale_date=date(2026, 6, 11 + index), price=Decimal("20.00"), channel=SaleRecord.Channel.EBAY_AU)

    response = api_client.get("/api/profit/ledger/")

    assert response.status_code == 200, response.data
    rows = {row["title"]: row for row in response.data["ledger"]}
    assert rows["Inherited source"]["source_name"] == "Estate A"
    by_source = {row["label"]: row for row in response.data["aggregates"]["by_source"]}
    assert by_source["Estate A"]["sale_count"] == 3

    groups = {
        (row["category"], row["channel"], row["source_name"]): row
        for row in response.data["buy_more"]["groups"]
    }
    assert groups[(category.name, SaleRecord.Channel.EBAY_AU, "Estate A")]["status"] == "ranked"
    assert groups[(category.name, SaleRecord.Channel.EBAY_AU, "Estate A")]["recommended"] is True
    assert groups[(category.name, SaleRecord.Channel.EBAY_AU, "Auction B")]["status"] == "loss_making"
    assert groups[(category.name, SaleRecord.Channel.EBAY_AU, "Auction B")]["recommended"] is False


def test_lot_mode_max_buy_uses_shared_engine_and_what_if_stays_transient(api_client, setting):
    payload = {
        "lot_mode": True,
        "expected_sell_price": "100.00",
        "price_basis": "seller_receives",
        "seller_mode": ProfitSetting.SellerMode.FREE_SELLING,
        "asking_price": "60.00",
        "postage": "0.00",
        "packaging": "0.00",
        "refurb": "0.00",
        "target_type": "roi",
        "roi_pct": "30.00",
        "roi_basis": ProfitSetting.RoiBasis.ALL_IN_CASH,
        "evidence_source": "what_if",
        "confidence_label": "lot what-if (your estimate)",
    }
    response = api_client.post("/api/buy-calculator/calculate/", payload, format="json")

    assert response.status_code == 200, response.data
    assert response.data["max_buy"] == "76.92"
    assert response.data["headline"] == "Max Lot Buy"
    assert response.data["confidence_label"] == "lot what-if (your estimate)"
    assert Lot.objects.count() == 0
    assert Source.objects.count() == 0


def test_no_new_network_calls_in_lot_profit_paths():
    import apps.profit.lots as lots

    source = inspect.getsource(lots) + inspect.getsource(ledger)
    for token in ["requests", "httpx", "urlopen", "urllib.request", "ebay_sdk", "openai"]:
        assert token not in source


def api_profit_for_title(title: str) -> str:
    rows = ledger.ledger_rows(ProfitSetting.objects.order_by("-updated_at").first() or ProfitSetting())
    return next(row for row in rows if row["title"] == title)["realised_profit"]
