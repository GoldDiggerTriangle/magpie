from decimal import Decimal

import pytest
from django.core.management import call_command
from django.db import IntegrityError, transaction
from rest_framework.test import APIClient

from apps.catalog.models import ProductCategory
from apps.core.backup_ops import DB_SNAPSHOT_NAME
from apps.core.tests.backup_helpers import (
    load_backup_manifest,
    run_encrypted_backup,
    sqlite_count,
)
from apps.inventory.models import InventoryItem
from apps.research.models import Comparable, ResearchRecord
from apps.valuation.models import FeeSchedule, ValuationComparable, ValuationReport
from apps.valuation.services import calculate_profit, set_current
from apps.valuation.strategies import (
    CommodityManualStrategy,
    CompBasedStrategy,
    get_strategy,
)


@pytest.fixture
def user(django_user_model):
    return django_user_model.objects.create_user(username="valuer", password="pass")


@pytest.fixture
def api_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def category():
    return ProductCategory.objects.create(name="Coins", slug="coins-s2", sku_prefix="COIN")


@pytest.fixture
def item(category):
    return InventoryItem.objects.create(
        title="Research coin",
        category=category,
        acquisition_cost=Decimal("20.00"),
        refurb_cost=Decimal("5.00"),
        inbound_shipping_cost=Decimal("3.00"),
    )


@pytest.fixture
def schedule():
    return FeeSchedule.objects.create(
        name="Test schedule",
        effective_from="2026-01-01",
        final_value_pct=Decimal("10.000"),
        per_order_fee=Decimal("1.00"),
        promoted_pct=Decimal("2.000"),
        gst_pct=Decimal("10.000"),
        default_outbound_shipping=Decimal("10.00"),
        default_packaging_cost=Decimal("2.00"),
    )


def make_comp(item, price, kind=Comparable.Kind.SOLD, title="Comp"):
    return Comparable.objects.create(
        item=item,
        kind=kind,
        title=f"{title} {price}",
        source="Manual",
        price=Decimal(price),
    )


@pytest.mark.django_db
def test_model_constraints_for_current_report_and_report_comparable(item, schedule):
    ValuationReport.objects.create(
        item=item,
        fee_schedule=schedule,
        is_current=True,
        estimate_median=Decimal("50.00"),
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            ValuationReport.objects.create(
                item=item,
                fee_schedule=schedule,
                is_current=True,
                estimate_median=Decimal("60.00"),
            )

    report = ValuationReport.objects.create(item=item, fee_schedule=schedule)
    comp = make_comp(item, "40.00")
    ValuationComparable.objects.create(report=report, comparable=comp)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            ValuationComparable.objects.create(report=report, comparable=comp)


@pytest.mark.django_db
def test_fee_calculator_uses_schedule_values_and_zero_price_guard(schedule):
    breakdown = calculate_profit(
        sale_price=Decimal("100.00"),
        true_cost=Decimal("40.00"),
        schedule=schedule,
        outbound_shipping=Decimal("5.00"),
        packaging=Decimal("1.00"),
    )

    assert breakdown.final_value_fee == Decimal("10.50")
    assert breakdown.per_order_fee == Decimal("1.00")
    assert breakdown.promoted_fee == Decimal("2.00")
    assert breakdown.gst_on_fees == Decimal("1.35")
    assert breakdown.total_deductions == Decimal("60.85")
    assert breakdown.net_profit == Decimal("39.15")
    assert breakdown.margin_pct == Decimal("0.3915")

    fallback = calculate_profit(
        sale_price=Decimal("100.00"),
        true_cost=Decimal("40.00"),
        schedule=schedule,
    )
    assert fallback.outbound_shipping == Decimal("10.00")
    assert fallback.packaging == Decimal("2.00")
    assert fallback.final_value_fee == Decimal("11.00")

    zero = calculate_profit(sale_price=Decimal("0"), true_cost=Decimal("0"), schedule=schedule)
    assert zero.margin_pct == Decimal("0")


@pytest.mark.django_db
def test_valuation_strategies(item):
    low = make_comp(item, "80.00", title="Low sold")
    high = make_comp(item, "100.00", title="High sold")
    excluded = make_comp(item, "1000.00", title="Excluded active", kind=Comparable.Kind.ACTIVE)

    result = CompBasedStrategy().estimate(
        item=item,
        included_comps=[low, high],
        inputs={},
    )
    assert result.low == Decimal("80.00")
    assert result.median == Decimal("90.00")
    assert result.high == Decimal("100.00")
    assert excluded.price == Decimal("1000.00")

    commodity = CommodityManualStrategy().estimate(
        item=item,
        included_comps=[],
        inputs={
            "metal": "gold",
            "weight_g": "10",
            "fineness": "0.5",
            "spot_price_per_g": "100",
            "buy_margin_pct": "10",
        },
    )
    assert commodity.median == Decimal("500.00")
    assert commodity.fast_sale == Decimal("450.00")

    with pytest.raises(ValueError):
        get_strategy("commodity_live").estimate(item=item, included_comps=[], inputs={})


@pytest.mark.django_db
def test_set_current_clears_previous_and_syncs_item_fields(item, schedule):
    old = ValuationReport.objects.create(
        item=item,
        fee_schedule=schedule,
        is_current=True,
        estimate_median=Decimal("50.00"),
        suggested_price=Decimal("55.00"),
        min_acceptable_price=Decimal("35.00"),
    )
    new = ValuationReport.objects.create(
        item=item,
        fee_schedule=schedule,
        estimate_median=Decimal("70.00"),
        suggested_price=Decimal("80.00"),
        min_acceptable_price=Decimal("60.00"),
    )

    set_current(new)
    old.refresh_from_db()
    item.refresh_from_db()

    assert old.is_current is False
    new.refresh_from_db()
    assert new.is_current is True
    assert item.estimated_value == Decimal("70.00")
    assert item.target_price == Decimal("80.00")
    assert item.min_price == Decimal("60.00")


@pytest.mark.django_db
def test_valuation_api_create_set_current_research_links_profit_and_validation(
    api_client,
    item,
    schedule,
):
    sold_one = make_comp(item, "70.00", title="Sold one")
    sold_two = make_comp(item, "90.00", title="Sold two")
    excluded = make_comp(item, "200.00", kind=Comparable.Kind.ACTIVE, title="Excluded")

    missing_reason = api_client.post(
        f"/api/items/{item.id}/valuation-reports/",
        {
            "strategy": "comp_based",
            "is_overridden": True,
            "comp_links": [{"comparable": str(sold_one.id), "included": True}],
        },
        format="json",
    )
    assert missing_reason.status_code == 400

    report_create = api_client.post(
        f"/api/items/{item.id}/valuation-reports/",
        {
            "strategy": "comp_based",
            "fee_schedule": str(schedule.id),
            "is_current": True,
            "confidence_score": 0.75,
            "confidence_reason": "Two sold comps.",
            "comp_links": [
                {"comparable": str(sold_one.id), "included": True},
                {"comparable": str(sold_two.id), "included": True},
                {
                    "comparable": str(excluded.id),
                    "included": False,
                    "exclude_reason": "Active asking price.",
                },
            ],
        },
        format="json",
    )
    assert report_create.status_code == 201, report_create.data
    assert Decimal(report_create.data["estimate_median"]) == Decimal("80.00")
    assert len(report_create.data["comp_links"]) == 3
    report_id = report_create.data["id"]

    item.refresh_from_db()
    assert item.estimated_value == Decimal("80.00")
    assert item.target_price == Decimal("80.00")

    profit = api_client.get(f"/api/valuation-reports/{report_id}/profit/", {"price": "100"})
    assert profit.status_code == 200
    assert Decimal(profit.data["true_cost"]) == Decimal("28.00")

    links = api_client.get(f"/api/items/{item.id}/research-links/")
    assert links.status_code == 200
    assert {link["label"] for link in links.data["links"]} >= {"eBay active", "Terapeak"}

    detail = api_client.get(f"/api/items/{item.id}/")
    assert detail.status_code == 200
    assert detail.data["comps_count"] == 3
    assert detail.data["current_valuation"]["id"] == report_id

    second = api_client.post(
        f"/api/items/{item.id}/valuation-reports/",
        {
            "strategy": "commodity_manual",
            "fee_schedule": str(schedule.id),
            "inputs": {
                "metal": "silver",
                "weight_g": "5",
                "fineness": "0.5",
                "spot_price_per_g": "10",
                "buy_margin_pct": "20",
            },
        },
        format="json",
    )
    assert second.status_code == 201, second.data
    set_current_response = api_client.post(
        f"/api/valuation-reports/{second.data['id']}/set-current/"
    )
    assert set_current_response.status_code == 200
    assert set_current_response.data["is_current"] is True


@pytest.mark.django_db
def test_fee_schedule_api_is_read_only(api_client, schedule):
    response = api_client.get("/api/fee-schedules/")
    assert response.status_code == 200
    assert response.data["count"] == 1

    create = api_client.post(
        "/api/fee-schedules/",
        {
            "name": "API should reject",
            "effective_from": "2026-02-01",
            "final_value_pct": "1.000",
        },
        format="json",
    )
    assert create.status_code == 405


@pytest.mark.django_db
def test_unauthenticated_valuation_api_rejected(item):
    client = APIClient()
    response = client.get(f"/api/items/{item.id}/valuation-reports/")
    assert response.status_code in {401, 403}


@pytest.mark.django_db(transaction=True)
def test_backup_json_restore_includes_sprint2_tables(tmp_path, monkeypatch, item, schedule):
    comp = make_comp(item, "80.00")
    ResearchRecord.objects.create(item=item, source="Manual", content="Restorable note.")
    report = ValuationReport.objects.create(
        item=item,
        fee_schedule=schedule,
        estimate_median=Decimal("80.00"),
    )
    ValuationComparable.objects.create(report=report, comparable=comp)

    _, extract_dir = run_encrypted_backup(tmp_path, monkeypatch)
    manifest = load_backup_manifest(extract_dir)

    assert "research.comparable" in manifest["row_counts"]
    assert "valuation.valuationreport" in manifest["row_counts"]
    restored_db = extract_dir / DB_SNAPSHOT_NAME
    assert sqlite_count(restored_db, "research_comparable") == 1
    assert sqlite_count(restored_db, "research_researchrecord") == 1
    assert sqlite_count(restored_db, "valuation_valuationreport") == 1
    assert sqlite_count(restored_db, "valuation_valuationcomparable") == 1
