from datetime import date
from decimal import Decimal

import pytest
from django.db import connection
from rest_framework.test import APIClient

from apps.catalog.models import ProductCategory
from apps.core.backup_ops import DB_SNAPSHOT_NAME
from apps.core.tests.backup_helpers import (
    load_backup_manifest,
    run_encrypted_backup,
    sqlite_count,
)
from apps.inventory.models import InventoryItem
from apps.sales.models import SaleRecord
from apps.sales.services import active_realised_profit, create_sale_record
from apps.valuation.models import FeeSchedule, ValuationReport


@pytest.fixture
def user(django_user_model):
    return django_user_model.objects.create_user(username="sales", password="pass")


@pytest.fixture
def api_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def category():
    return ProductCategory.objects.create(
        name="Sprint 10 Lots",
        slug="sprint-10-lots",
        sku_prefix="S10",
    )


@pytest.fixture
def fee_schedule():
    return FeeSchedule.objects.create(
        name="Sprint 10 fees",
        effective_from=date(2026, 1, 1),
        final_value_pct=Decimal("10.000"),
        per_order_fee=Decimal("0.30"),
        promoted_pct=Decimal("2.000"),
        gst_pct=Decimal("10.000"),
    )


def make_item(category, **overrides):
    data = {
        "title": "Bulk coin lot",
        "category": category,
        "status": InventoryItem.Status.READY_TO_LIST,
        "condition": InventoryItem.Condition.GOOD,
        "quantity_total": 10,
        "acquisition_cost": Decimal("100.00"),
        "estimated_value": Decimal("180.00"),
    }
    data.update(overrides)
    return InventoryItem.objects.create(**data)


def sale_payload(item, **overrides):
    data = {
        "item": item,
        "sale_date": date(2026, 6, 14),
        "quantity": 1,
        "sale_price": Decimal("50.00"),
        "channel": SaleRecord.Channel.MANUAL,
        "actual_fees_total": Decimal("5.00"),
        "actual_shipping_cost": Decimal("2.00"),
    }
    data.update(overrides)
    return data


@pytest.mark.django_db
def test_partial_sales_update_lifecycle_and_reject_oversell(category, fee_schedule):
    item = make_item(category, quantity_total=10, acquisition_cost=Decimal("100.00"))

    first = create_sale_record(
        data=sale_payload(
            item,
            quantity=3,
            sale_price=Decimal("90.00"),
            actual_fees_total=Decimal("9.00"),
            actual_shipping_cost=Decimal("6.00"),
        )
    )

    item.refresh_from_db()
    assert item.quantity_sold == 3
    assert item.quantity_remaining == 7
    assert item.status == InventoryItem.Status.PARTIALLY_SOLD
    assert first.net_proceeds == Decimal("75.00")
    assert first.allocated_cost_basis == Decimal("30.00")
    assert first.realised_profit == Decimal("45.00")

    create_sale_record(
        data=sale_payload(
            item,
            quantity=7,
            sale_price=Decimal("210.00"),
            actual_fees_total=Decimal("21.00"),
            actual_shipping_cost=Decimal("0.00"),
        )
    )
    item.refresh_from_db()
    assert item.quantity_sold == 10
    assert item.quantity_remaining == 0
    assert item.status == InventoryItem.Status.SOLD

    with pytest.raises(Exception, match="remaining available units"):
        create_sale_record(data=sale_payload(item, quantity=1))


@pytest.mark.django_db
def test_correction_rows_do_not_double_count_quantity_or_profit(category, fee_schedule):
    item = make_item(category, quantity_total=10, acquisition_cost=Decimal("100.00"))
    original = create_sale_record(
        data=sale_payload(
            item,
            quantity=3,
            sale_price=Decimal("90.00"),
            actual_fees_total=Decimal("0.00"),
            actual_shipping_cost=Decimal("0.00"),
        )
    )

    correction = create_sale_record(
        data=sale_payload(
            item,
            quantity=4,
            sale_price=Decimal("120.00"),
            actual_fees_total=Decimal("0.00"),
            actual_shipping_cost=Decimal("0.00"),
        ),
        corrected_from=original,
    )

    item.refresh_from_db()
    original.refresh_from_db()
    assert original.is_superseded is True
    assert correction.corrected_from_id == original.id
    assert SaleRecord.objects.count() == 2
    assert item.quantity_sold == 4
    assert item.quantity_remaining == 6
    assert active_realised_profit(item) == Decimal("80.00")


@pytest.mark.django_db
def test_cost_basis_rounding_and_override(category, fee_schedule):
    item = make_item(category, quantity_total=6, acquisition_cost=Decimal("100.00"))

    proportional = create_sale_record(
        data=sale_payload(
            item,
            quantity=1,
            sale_price=Decimal("30.00"),
            actual_fees_total=Decimal("0.00"),
            actual_shipping_cost=Decimal("0.00"),
        )
    )
    assert proportional.allocated_cost_basis == Decimal("16.67")
    assert proportional.realised_profit == Decimal("13.33")

    override = create_sale_record(
        data=sale_payload(
            item,
            quantity=1,
            sale_price=Decimal("30.00"),
            actual_fees_total=Decimal("0.00"),
            actual_shipping_cost=Decimal("0.00"),
            cost_basis_override=Decimal("22.22"),
        )
    )
    assert override.allocated_cost_basis == Decimal("22.22")
    assert override.realised_profit == Decimal("7.78")


@pytest.mark.django_db
def test_snapshots_are_stable_after_valuation_and_fee_changes(category, fee_schedule):
    item = make_item(category)
    report = ValuationReport.objects.create(
        item=item,
        strategy=ValuationReport.Strategy.COMP_BASED,
        is_current=True,
        estimate_median=Decimal("175.00"),
        suggested_price=Decimal("190.00"),
        fee_schedule=fee_schedule,
    )

    sale = create_sale_record(
        data={
            "item": item,
            "sale_date": date(2026, 6, 14),
            "quantity": 1,
            "sale_price": Decimal("100.00"),
            "channel": SaleRecord.Channel.MANUAL,
            "actual_fees_total": None,
            "actual_shipping_cost": Decimal("0.00"),
        }
    )
    assert sale.valuation_snapshot["current_report"]["suggested_price"] == "190.00"
    assert sale.estimated_fee_snapshot["schedule"]["id"] == str(fee_schedule.id)
    assert sale.estimated_fee_snapshot["estimated_fees_total"] == "13.53"
    assert sale.actual_fees_total == Decimal("13.53")

    report.suggested_price = Decimal("250.00")
    report.save(update_fields=["suggested_price", "updated_at"])
    fee_schedule.final_value_pct = Decimal("15.000")
    fee_schedule.save(update_fields=["final_value_pct", "updated_at"])

    sale.refresh_from_db()
    assert sale.valuation_snapshot["current_report"]["suggested_price"] == "190.00"
    assert sale.estimated_fee_snapshot["schedule"]["final_value_pct"] == "10.000"
    assert sale.estimated_fee_snapshot["estimated_fees_total"] == "13.53"


@pytest.mark.django_db
def test_sales_api_create_list_and_correct(api_client, category, fee_schedule):
    item = make_item(category, quantity_total=5, acquisition_cost=Decimal("50.00"))

    response = api_client.post(
        f"/api/items/{item.id}/sales/",
        {
            "sale_date": "2026-06-14",
            "quantity": 2,
            "sale_price": "80.00",
            "channel": "manual",
            "actual_fees_total": "8.00",
            "actual_shipping_cost": "5.00",
            "notes": "counter sale",
        },
        format="json",
    )
    assert response.status_code == 201, response.data
    sale_id = response.data["id"]
    assert response.data["quantity"] == 2
    assert response.data["allocated_cost_basis"] == "20.00"
    item.refresh_from_db()
    assert item.status == InventoryItem.Status.PARTIALLY_SOLD

    correction = api_client.post(
        f"/api/sales/{sale_id}/correct/",
        {
            "sale_date": "2026-06-14",
            "quantity": 3,
            "sale_price": "120.00",
            "channel": "manual",
            "actual_fees_total": "12.00",
            "actual_shipping_cost": "5.00",
        },
        format="json",
    )
    assert correction.status_code == 201, correction.data
    assert correction.data["corrected_from"] == sale_id
    item.refresh_from_db()
    assert item.quantity_sold == 3
    assert item.quantity_remaining == 2

    list_response = api_client.get(f"/api/items/{item.id}/sales/")
    assert list_response.status_code == 200
    assert list_response.data["count"] == 2
    superseded = [row for row in list_response.data["results"] if row["id"] == sale_id][0]
    assert superseded["is_superseded"] is True


@pytest.mark.django_db(transaction=True)
def test_backup_restore_includes_sales_table(tmp_path, monkeypatch, category, fee_schedule):
    if connection.vendor != "sqlite":
        pytest.skip("Sprint 8 backup command is SQLite-only.")

    item = make_item(category, quantity_total=2, acquisition_cost=Decimal("20.00"))
    create_sale_record(
        data=sale_payload(
            item,
            quantity=1,
            sale_price=Decimal("40.00"),
            actual_fees_total=Decimal("4.00"),
            actual_shipping_cost=Decimal("0.00"),
        )
    )

    _, extract_dir = run_encrypted_backup(tmp_path, monkeypatch)
    manifest = load_backup_manifest(extract_dir)
    assert manifest["row_counts"]["sales.salerecord"] == 1
    assert sqlite_count(extract_dir / DB_SNAPSHOT_NAME, "sales_salerecord") == 1
