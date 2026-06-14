from datetime import date, timedelta
from decimal import Decimal
import json

import pytest
from django.db import connection
from django.urls import resolve
from django.utils import timezone
from rest_framework.test import APIClient

import apps.ebay.adapters as ebay_adapters
from apps.audit.models import AuditLog
from apps.catalog.models import ProductCategory
from apps.core.backup_ops import DB_SNAPSHOT_NAME
from apps.core.tests.backup_helpers import (
    load_backup_manifest,
    run_encrypted_backup,
    sqlite_count,
)
from apps.ebay.constants import (
    AUDIT_ORDER_DUPLICATE_FLAGGED,
    AUDIT_ORDER_STAGING_RESOLVED,
    AUDIT_ORDER_SYNC_COMPLETED,
    EBAY_SCOPES,
)
from apps.ebay.models import (
    EbayCredential,
    EbayOrderDuplicateCandidate,
    EbayOrderStaging,
    EbayOrderSyncState,
)
from apps.ebay.order_sync import resolve_staging, sync_orders
from apps.inventory.models import InventoryItem
from apps.listing.models import ListingDraft
from apps.sales.models import SaleRecord
from apps.sales.services import create_sale_record
from apps.valuation.models import FeeSchedule, ValuationReport


TEST_FERNET_KEY = "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY="


@pytest.fixture(autouse=True)
def ebay_settings(settings):
    settings.EBAY_ENV = ""
    settings.EBAY_CLIENT_ID = ""
    settings.EBAY_CLIENT_SECRET = ""
    settings.EBAY_RU_NAME = ""
    settings.MAGPIE_TOKEN_ENCRYPTION_KEY = TEST_FERNET_KEY
    ebay_adapters.FakeEbayOrderAdapter.orders = []
    ebay_adapters.FakeEbayOrderAdapter.call_count = 0
    ebay_adapters.FakeEbayOrderAdapter.last_start = None
    ebay_adapters.FakeEbayOrderAdapter.last_end = None
    ebay_adapters.FakeEbayFinancesAdapter.transactions = []
    ebay_adapters.FakeEbayFinancesAdapter.call_count = 0
    ebay_adapters.FakeEbayFinancesAdapter.last_start = None
    ebay_adapters.FakeEbayFinancesAdapter.last_end = None


@pytest.fixture
def user(django_user_model):
    return django_user_model.objects.create_user(username="sprint11", password="pass")


@pytest.fixture
def api_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def credential():
    return EbayCredential.objects.create(
        environment="sandbox",
        scopes=EBAY_SCOPES,
        refresh_token="refresh-token",
        access_token="access-token",
        access_token_expires_at=timezone.now() + timedelta(hours=1),
    )


@pytest.fixture
def old_scope_credential():
    return EbayCredential.objects.create(
        environment="sandbox",
        scopes=EBAY_SCOPES[:2],
        refresh_token="refresh-token",
        access_token="access-token",
        access_token_expires_at=timezone.now() + timedelta(hours=1),
    )


@pytest.fixture
def category():
    return ProductCategory.objects.create(name="Sprint 11", slug="sprint-11", sku_prefix="S11")


@pytest.fixture
def fee_schedule():
    return FeeSchedule.objects.create(
        name="Sprint 11 fees",
        effective_from=date(2026, 1, 1),
        final_value_pct=Decimal("10.000"),
        per_order_fee=Decimal("0.30"),
        promoted_pct=Decimal("0.000"),
        gst_pct=Decimal("10.000"),
    )


def make_item(category, **overrides):
    data = {
        "title": "Sync lot",
        "category": category,
        "status": InventoryItem.Status.LISTED,
        "condition": InventoryItem.Condition.GOOD,
        "quantity_total": 10,
        "acquisition_cost": Decimal("100.00"),
        "estimated_value": Decimal("200.00"),
    }
    data.update(overrides)
    return InventoryItem.objects.create(**data)


def fake_order(*, sku, order_id="ORDER-1", line_id="LINE-1", quantity=3, price="90.00"):
    return {
        "orderId": order_id,
        "creationDate": "2026-06-14T02:00:00.000Z",
        "buyer": {"taxAddress": {"countryCode": "AU"}},
        "lineItems": [
            {
                "lineItemId": line_id,
                "sku": sku,
                "title": f"Order line {sku}",
                "quantity": quantity,
                "lineItemCost": {"value": price, "currency": "AUD"},
            }
        ],
    }


def fake_finance(
    *,
    order_id="ORDER-1",
    line_id="LINE-1",
    transaction_id="TXN-1",
    fee="9.00",
):
    return {
        "transactionId": transaction_id,
        "transactionType": "SALE",
        "orderId": order_id,
        "orderLineItems": [{"lineItemId": line_id}],
        "fees": [{"type": "final_value_fee", "amount": {"value": fee, "currency": "AUD"}}],
    }


@pytest.mark.django_db
def test_fake_sync_matched_partial_sale_idempotency_snapshots_and_local_listing_state(
    credential,
    category,
    fee_schedule,
):
    item = make_item(category)
    ValuationReport.objects.create(
        item=item,
        strategy=ValuationReport.Strategy.COMP_BASED,
        is_current=True,
        suggested_price=Decimal("120.00"),
        fee_schedule=fee_schedule,
    )
    draft = ListingDraft.objects.create(
        item=item,
        status=ListingDraft.Status.PUBLISHED,
        channel_data={"listing_id": "listing-1", "inventory_item_sku": item.sku},
        title="Published sync lot",
        price=Decimal("100.00"),
    )
    ebay_adapters.FakeEbayOrderAdapter.orders = [fake_order(sku=item.sku)]
    ebay_adapters.FakeEbayFinancesAdapter.transactions = [fake_finance()]

    result = sync_orders(actor="pytest")

    assert result["counts"]["created"] == 1
    sale = SaleRecord.objects.get()
    assert sale.provenance == SaleRecord.Provenance.EBAY_SYNC
    assert sale.quantity == 3
    assert sale.sale_price == Decimal("90.00")
    assert sale.actual_fees_total == Decimal("9.00")
    assert sale.fee_status == SaleRecord.FeeStatus.AUTHORITATIVE
    assert sale.ebay_order_id == "ORDER-1"
    assert sale.ebay_line_item_id == "LINE-1"
    assert sale.ebay_transaction_id == "TXN-1"
    assert sale.valuation_snapshot["current_report"]["suggested_price"] == "120.00"
    assert sale.estimated_fee_snapshot["schedule"]["id"] == str(fee_schedule.id)

    item.refresh_from_db()
    assert item.quantity_sold == 3
    assert item.quantity_remaining == 7
    assert item.status == InventoryItem.Status.PARTIALLY_SOLD
    draft.refresh_from_db()
    assert draft.channel_data["last_ebay_order_id"] == "ORDER-1"
    assert draft.channel_data["last_ebay_line_item_id"] == "LINE-1"

    rerun = sync_orders(actor="pytest")
    assert rerun["counts"]["skipped"] == 1
    assert SaleRecord.objects.count() == 1
    assert EbayOrderStaging.objects.count() == 0
    assert AuditLog.objects.filter(action=AUDIT_ORDER_SYNC_COMPLETED).count() == 2
    assert_audit_secret_free()


@pytest.mark.django_db
def test_unmatched_order_stages_and_conservative_fee_mapping_is_reviewable(
    credential,
):
    ebay_adapters.FakeEbayOrderAdapter.orders = [
        fake_order(sku="UNKNOWN-SKU", order_id="ORDER-2", line_id="LINE-2", price="40.00")
    ]
    ebay_adapters.FakeEbayFinancesAdapter.transactions = [
        {
            "transactionId": "TXN-2",
            "orderId": "ORDER-2",
            "fees": [{"type": "final_value_fee", "amount": {"value": "4.00"}}],
        },
        {
            "transactionId": "TXN-3",
            "orderId": "ORDER-2",
            "fees": [{"type": "final_value_fee", "amount": {"value": "1.00"}}],
        },
    ]

    result = sync_orders(actor="pytest")

    assert result["counts"]["staged"] == 1
    assert result["counts"]["fee_estimated_or_unmapped"] == 1
    staging = EbayOrderStaging.objects.get()
    assert staging.status == EbayOrderStaging.Status.PENDING
    assert staging.sku == "UNKNOWN-SKU"
    assert staging.fee_status == SaleRecord.FeeStatus.ESTIMATED_OR_UNMAPPED
    assert staging.actual_fee is None
    assert staging.finance_snapshot["join_status"] == "unmapped"
    rerun = sync_orders(actor="pytest")
    assert rerun["counts"]["skipped"] == 1
    assert EbayOrderStaging.objects.count() == 1


@pytest.mark.django_db
def test_matched_order_with_uncertain_finance_keeps_estimated_fee_status(
    credential,
    category,
    fee_schedule,
):
    item = make_item(category)
    ebay_adapters.FakeEbayOrderAdapter.orders = [
        fake_order(sku=item.sku, order_id="ORDER-FEE", line_id="LINE-FEE", price="70.00")
    ]
    ebay_adapters.FakeEbayFinancesAdapter.transactions = [
        {
            "transactionId": "TXN-A",
            "orderId": "ORDER-FEE",
            "fees": [{"type": "final_value_fee", "amount": {"value": "7.00"}}],
        },
        {
            "transactionId": "TXN-B",
            "orderId": "ORDER-FEE",
            "fees": [{"type": "fixed_fee", "amount": {"value": "0.30"}}],
        },
    ]

    result = sync_orders(actor="pytest")

    assert result["counts"]["created"] == 1
    assert result["counts"]["fee_estimated_or_unmapped"] == 1
    sale = SaleRecord.objects.get()
    assert sale.fee_status == SaleRecord.FeeStatus.ESTIMATED_OR_UNMAPPED
    assert sale.ebay_transaction_id == ""
    assert sale.actual_fees_total == Decimal(sale.estimated_fee_snapshot["estimated_fees_total"])
    assert sale.channel_data["ebay_finance_snapshot"]["join_status"] == "unmapped"


@pytest.mark.django_db
def test_sync_uses_90_day_first_window_then_watermark_lookback(credential):
    result = sync_orders(actor="pytest")
    first_start = ebay_adapters.FakeEbayOrderAdapter.last_start
    first_end = ebay_adapters.FakeEbayOrderAdapter.last_end
    assert result["start"] == first_start.isoformat()
    assert result["end"] == first_end.isoformat()
    assert timedelta(days=89, hours=23) < (first_end - first_start) < timedelta(days=90, minutes=1)

    state = EbayOrderSyncState.objects.get(environment="sandbox")
    state.last_synced_at = timezone.now() - timedelta(days=10)
    state.lookback_days = 3
    state.save(update_fields=["last_synced_at", "lookback_days", "updated_at"])

    result = sync_orders(actor="pytest")
    next_start = ebay_adapters.FakeEbayOrderAdapter.last_start
    assert result["start"] == next_start.isoformat()
    assert timedelta(days=12, hours=23) < (timezone.now() - next_start) < timedelta(days=13, minutes=1)


@pytest.mark.django_db
def test_staging_resolution_link_quick_create_and_external_profit_flags(
    credential,
    category,
    fee_schedule,
):
    item = make_item(category)
    linked = EbayOrderStaging.objects.create(
        ebay_order_id="ORDER-LINK",
        ebay_line_item_id="LINE-LINK",
        sku="UNKNOWN-LINK",
        quantity=1,
        line_price=Decimal("50.00"),
        sale_date=date(2026, 6, 14),
        actual_fee=Decimal("5.00"),
        fee_status=SaleRecord.FeeStatus.AUTHORITATIVE,
    )
    quick = EbayOrderStaging.objects.create(
        ebay_order_id="ORDER-QUICK",
        ebay_line_item_id="LINE-QUICK",
        sku="UNKNOWN-QUICK",
        quantity=2,
        line_price=Decimal("80.00"),
        sale_date=date(2026, 6, 14),
    )
    external = EbayOrderStaging.objects.create(
        ebay_order_id="ORDER-EXT",
        ebay_line_item_id="LINE-EXT",
        sku="OLD-STORE",
        quantity=1,
        line_price=Decimal("25.00"),
        sale_date=date(2026, 6, 14),
    )

    linked_sale = resolve_staging(linked, action="link", item=item, actor="pytest")
    quick_sale = resolve_staging(
        quick,
        action="quick_create",
        actor="pytest",
        item_data={"title": "Quick created item", "acquisition_cost": Decimal("10.00")},
    )
    external_sale = resolve_staging(external, action="mark_external", actor="pytest")

    assert linked_sale.item_id == item.id
    assert linked_sale.actual_fees_total == Decimal("5.00")
    assert quick_sale.item is not None
    assert quick_sale.item.title == "Quick created item"
    assert quick_sale.item.quantity_total == 2
    assert external_sale.item is None
    assert external_sale.is_external is True
    assert external_sale.cost_basis_unknown is True
    assert external_sale.allocated_cost_basis is None
    assert external_sale.realised_profit is None
    assert EbayOrderStaging.objects.filter(status=EbayOrderStaging.Status.RESOLVED).count() == 3
    assert AuditLog.objects.filter(action=AUDIT_ORDER_STAGING_RESOLVED).count() == 3


@pytest.mark.django_db
def test_duplicate_candidates_are_flagged_not_auto_merged(credential, category, fee_schedule):
    item = make_item(category, quantity_total=1, acquisition_cost=Decimal("20.00"))
    manual = create_sale_record(
        data={
            "item": item,
            "sale_date": date(2026, 6, 14),
            "quantity": 1,
            "sale_price": Decimal("50.00"),
            "channel": SaleRecord.Channel.MANUAL,
            "actual_fees_total": Decimal("5.00"),
            "actual_shipping_cost": Decimal("0.00"),
        }
    )
    item.status = InventoryItem.Status.LISTED
    item.quantity_total = 2
    item.save(update_fields=["status", "quantity_total", "updated_at"])
    ebay_adapters.FakeEbayOrderAdapter.orders = [
        fake_order(sku=item.sku, order_id="ORDER-DUP", line_id="LINE-DUP", quantity=1, price="50.00")
    ]

    result = sync_orders(actor="pytest")

    assert result["counts"]["duplicate_flagged"] == 1
    assert SaleRecord.objects.count() == 1
    candidate = EbayOrderDuplicateCandidate.objects.get()
    assert candidate.manual_sale_id == manual.id
    assert candidate.item_id == item.id
    assert AuditLog.objects.filter(action=AUDIT_ORDER_DUPLICATE_FLAGGED).exists()


@pytest.mark.django_db
def test_sync_requires_incremental_reconsent_for_order_scopes(old_scope_credential):
    with pytest.raises(ebay_adapters.EbayUnavailable, match="re-consent"):
        sync_orders(actor="pytest")

    status_payload = json.dumps(list(AuditLog.objects.values_list("payload", flat=True)))
    assert "refresh-token" not in status_payload


@pytest.mark.django_db
def test_order_sync_api_and_staging_resolution_paths(
    api_client,
    credential,
    category,
    fee_schedule,
):
    item = make_item(category)
    ebay_adapters.FakeEbayOrderAdapter.orders = [
        fake_order(sku=item.sku, order_id="ORDER-API", line_id="LINE-API", quantity=1, price="30.00")
    ]
    sync_response = api_client.post("/api/ebay/orders/sync/", {}, format="json")
    assert sync_response.status_code == 200, sync_response.data
    assert sync_response.data["counts"]["created"] == 1

    staging = EbayOrderStaging.objects.create(
        ebay_order_id="ORDER-API-STAGE",
        ebay_line_item_id="LINE-API-STAGE",
        sku="NOPE",
        quantity=1,
        line_price=Decimal("30.00"),
        sale_date=date(2026, 6, 14),
    )
    mark_external = api_client.post(
        f"/api/ebay/order-staging/{staging.id}/resolve/",
        {"action": "mark_external"},
        format="json",
    )
    assert mark_external.status_code == 201, mark_external.data
    assert mark_external.data["is_external"] is True
    assert mark_external.data["realised_profit"] is None
    assert resolve("/api/ebay/orders/sync/").url_name == "ebay-orders-sync"


@pytest.mark.django_db(transaction=True)
def test_backup_includes_order_staging_and_duplicate_tables(
    tmp_path,
    monkeypatch,
    credential,
    category,
    fee_schedule,
):
    if connection.vendor != "sqlite":
        pytest.skip("Sprint 8 backup command is SQLite-only.")
    item = make_item(category)
    manual = create_sale_record(
        data={
            "item": item,
            "sale_date": date(2026, 6, 14),
            "quantity": 1,
            "sale_price": Decimal("50.00"),
            "channel": SaleRecord.Channel.MANUAL,
            "actual_fees_total": Decimal("5.00"),
            "actual_shipping_cost": Decimal("0.00"),
        }
    )
    EbayOrderStaging.objects.create(
        ebay_order_id="ORDER-BACKUP",
        ebay_line_item_id="LINE-BACKUP",
        quantity=1,
        line_price=Decimal("50.00"),
        sale_date=date(2026, 6, 14),
    )
    EbayOrderDuplicateCandidate.objects.create(
        ebay_order_id="ORDER-BACKUP-DUP",
        ebay_line_item_id="LINE-BACKUP-DUP",
        item=item,
        manual_sale=manual,
        quantity=1,
        line_price=Decimal("50.00"),
        sale_date=date(2026, 6, 14),
    )

    _, extract_dir = run_encrypted_backup(tmp_path, monkeypatch)
    manifest = load_backup_manifest(extract_dir)
    assert manifest["row_counts"]["ebay.ebayorderstaging"] == 1
    assert manifest["row_counts"]["ebay.ebayorderduplicatecandidate"] == 1
    assert sqlite_count(extract_dir / DB_SNAPSHOT_NAME, "ebay_ebayorderstaging") == 1
    assert sqlite_count(extract_dir / DB_SNAPSHOT_NAME, "ebay_ebayorderduplicatecandidate") == 1


def assert_audit_secret_free():
    payloads = json.dumps(list(AuditLog.objects.values_list("payload", flat=True))).lower()
    for forbidden in ["refresh-token", "access-token", "secret", "auth-code"]:
        assert forbidden not in payloads
