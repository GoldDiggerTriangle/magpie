import copy
import inspect
import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from django.db import connections, DatabaseError
from django.core.exceptions import ValidationError
from rest_framework.test import APIClient

from apps.catalog.models import ProductCategory
from apps.inventory.models import InventoryItem
from apps.profit.ledger import ledger_rows
from apps.profit.models import ProfitSetting
from apps.sales.models import SaleRecord
from apps.sales.services import create_sale_record
from apps.valuation import fee_engine as engine
from apps.valuation.fee_math import calculate_order, allocate
from apps.valuation.fee_models import FeeScheduleVersion, FeeOrderSnapshot, SaleFeeSnapshot, FeeAdjustment, FeePlanPeriod, fee_writes
from apps.valuation.models import FeeSchedule
from apps.ebay.tests.test_sprint25_publish import concurrent_draft

pytestmark = pytest.mark.django_db
FIXTURE = json.loads((Path(__file__).resolve().parents[4] / "frontend/src/fixtures/sprint25FeeParity.json").read_text())


def payload(start="2026-01-01", end=None):
    return {"previous_id": None, "label": "Fixture calendar", "source_note": "Test values only", "periods": [{"plan": "pro_basic", "effective_from": start, "effective_to": end,
            "per_order_fee": "0.33", "international_pct": "1.1", "gst_treatment": "inclusive", "source_note": "Fixture dates confirmed", "rates": [copy.deepcopy(FIXTURE["rates"]["tier4"])]}]}


@pytest.fixture
def item():
    category = ProductCategory.objects.create(name="Coins", slug="coins", profile_key="coins", sku_prefix="FEE")
    return InventoryItem.objects.create(title="Owned fixture coin", category=category, acquisition_cost=Decimal("20"), quantity_total=20)


@pytest.mark.parametrize("case", FIXTURE["cases"], ids=lambda c: c["id"])
def test_shared_fee_parity(case):
    result = calculate_order(case["order"], FIXTURE["period"], FIXTURE["rates"])
    assert result["fee_total"] == case["total"]
    assert result["gst_added"] == "0.00"
    assert sum(Decimal(l["components"]["per_order_fee"]) for l in result["lines"].values()) == Decimal("0.33")
    if "revenue" in case:
        assert result["lines"]["a"]["revenue"] == case["revenue"]
        assert result["lines"]["a"]["fee_base"] == case["base"]


def test_allocations_conserve_every_cent():
    assert allocate(Decimal("0.01"), [1, 1, 1]) == [Decimal("0.01"), 0, 0]
    for n in range(1, 25):
        assert sum(allocate(Decimal("17.13"), list(range(1, n + 1)))) == Decimal("17.13")


def test_periods_boundaries_gaps_and_version_immutability():
    p = payload(end="2026-07-01")
    p["periods"].append({**p["periods"][0], "effective_from": "2026-07-02", "effective_to": None})
    v = engine.create_version(p)
    order = {"sale_date": "2026-06-30", "destination_country": "AU", "lines": [{"key": "x", "quantity": 1, "item_total": "100", "category_slug": "coins"}]}
    assert engine.evaluate_order(order)[0]["fee_total"] == "13.42"
    assert engine.evaluate_order({**order, "sale_date": "2026-07-01"})[0]["state"] == "schedule unknown"
    assert engine.evaluate_order({**order, "sale_date": "2026-07-02"})[0]["fee_total"] == "13.42"
    with pytest.raises(ValidationError):
        v.save()
    with pytest.raises(ValidationError):
        FeeScheduleVersion.objects.filter(pk=v.pk).update(label="mutated")
    with pytest.raises(ValidationError):
        v.periods.all().delete()
    with pytest.raises(ValidationError):
        FeePlanPeriod.objects.create(version=v, plan="pro_basic", effective_from=date(2026, 1, 1), per_order_fee=0, international_pct=0, source_note="bypass")
    bad = payload(); bad["periods"] *= 2
    with pytest.raises(ValueError, match="overlap"):
        engine.create_version(bad)
    assert FeeScheduleVersion.objects.count() == 1


def test_new_version_cannot_borrow_old_rates_and_conflicts_are_named():
    v = engine.create_version(payload())
    p = payload(); p.update(previous_id=str(v.pk)); p["periods"][0]["rates"] = []
    engine.create_version(p)
    order = {"sale_date": "2026-02-01", "destination_country": "AU", "lines": [{"key": "a", "quantity": 1, "item_total": "100", "category_slug": "coins"}]}
    assert engine.evaluate_order(order)[0]["fee_total"] is None
    assert engine.evaluate_order(order)[0]["state"] == "fee rate not configured"
    old = engine.evaluate_order({**order, "lines": [{**order["lines"][0], "ebay_category_id": "9355", "ebay_path": ["15032"]}]}, v)[0]
    assert old["category_conflicts"] == ["a"] and old["fee_total"] is None
    for category in ("phones-electronics", "tools", "unmapped"):
        assert engine.evaluate_order({**order, "lines": [{**order["lines"][0], "category_slug": category}]}, v)[0]["fee_total"] is None


def test_plan_restriction_is_not_an_auth_error():
    p = payload(); p["periods"][0]["plan"] = "pro_starter"
    engine.create_version(p)
    result = engine.evaluate_order({"sale_date": "2026-02-01", "destination_country": "AU", "lines": [{"key": "a", "quantity": 1, "item_total": "100", "category_slug": "coins"}]})[0]
    assert result["state"] == "plan restriction" and "not a reconnect error" in result["label"]


def test_sale_snapshots_freeze_math_costs_and_category_then_audit_adjustment(item):
    v = engine.create_version(payload())
    sale = create_sale_record(data={"item": item, "sale_date": date(2026, 2, 1), "sale_price": Decimal("100"), "quantity": 1,
        "channel": "ebay_au", "actual_fees_total": None, "fee_context": {"destination_country": "AU", "postage": "0"}})
    original = copy.deepcopy(sale.fee_snapshot.result)
    assert sale.fee_snapshot.provenance == "calculated"
    assert original["fees"] == "13.42"
    old_profit = sale.realised_profit
    item.acquisition_cost = Decimal("999"); item.category = None; item.save()
    p = payload(); p["previous_id"] = str(v.pk); p["periods"][0]["rates"][0] = {**p["periods"][0]["rates"][0], "fvf_pct": "99"}
    engine.create_version(p)
    sale.refresh_from_db()
    assert sale.realised_profit == old_profit
    assert sale.fee_snapshot.result == original and sale.fee_snapshot.version_id == v.pk
    updated = engine.adjust_fee(sale.fee_snapshot, {"amount": "-1.00", "reason": "Recorded fee credit", "provenance": "actual_recorded"})
    assert updated["fees"] == "12.42"
    assert Decimal(updated["realised_profit"]) == old_profit + 1
    assert SaleFeeSnapshot.objects.get(sale=sale).result == original
    assert FeeAdjustment.objects.count() == 1


def test_actual_fee_wins_and_unknown_is_not_zero(item):
    FeeSchedule.objects.create(name="Unverified legacy", effective_from=date(2020, 1, 1), final_value_pct=99)
    sale = create_sale_record(data={"item": item, "sale_date": date(2026, 2, 1), "sale_price": Decimal("100"), "quantity": 1,
        "actual_fees_total": None, "fee_context": {"destination_country": "AU"}})
    assert sale.realised_profit is None and sale.fee_snapshot.result["fees"] is None
    assert sale.estimated_fee_snapshot["estimated_fees_total"] is None
    assert sale.fee_snapshot.label == "schedule unknown"
    engine.create_version(payload())
    actual = create_sale_record(data={"item": item, "sale_date": date(2026, 2, 1), "sale_price": Decimal("100"), "quantity": 1,
        "actual_fees_total": Decimal("5"), "fee_context": {"destination_country": "AU"}})
    assert actual.fee_snapshot.result["fees"] == "5.00" and actual.fee_snapshot.provenance == "actual_recorded"


def test_legacy_copy_is_exact_not_a_pro_calculation(item):
    copies = []
    for i in range(4):
        sale = SaleRecord.objects.create(item=item if i < 3 else None, is_external=i == 3, cost_basis_unknown=i == 3, quantity=1, sale_date=date(2025, 6, 1), sale_price=1,
            actual_fees_total=Decimal("0.46"), estimated_fee_snapshot={"estimated_fees_total": "0.52", "schedule": {"name": "legacy"}}, actual_fee_breakdown={"recorded": "0.46"})
        copies.append({"sale_id": str(sale.pk), "actual_fees_total": "0.46", "actual_fee_breakdown": sale.actual_fee_breakdown, "estimated_fee_snapshot": sale.estimated_fee_snapshot,
            "result": {"revenue": "1.00", "fees": "0.46", "fee_provenance": "actual_recorded", "total_costs": "0.20" if i < 3 else None,
                       "realised_profit": "0.34" if i < 3 else None, "all_in_roi": "170.00" if i < 3 else None, "cost_state": "known" if i < 3 else "unknown", "cost_components": {"acquisition": "0.20"}}})
    before = list(SaleRecord.objects.values())
    assert engine.freeze_legacy_copies({"legacy_copies": copies}) == 4
    assert list(SaleRecord.objects.values()) == before
    for snapshot in SaleFeeSnapshot.objects.all():
        assert snapshot.label == engine.LEGACY_LABEL and snapshot.version_id is None
        assert snapshot.inputs["estimated_fee_snapshot"]["estimated_fees_total"] == "0.52"
        assert snapshot.inputs["actual_fees_total"] == "0.46"
    assert sorted(s.realised_profit for s in SaleRecord.objects.filter(item=item)) == [Decimal("0.34")] * 3
    assert SaleRecord.objects.get(item=None).realised_profit is None


def test_privacy_model_boundary_and_no_network(item, monkeypatch):
    import socket
    monkeypatch.setattr(socket.socket, "connect", lambda *args: pytest.fail("Network forbidden"))
    engine.create_version(payload())
    sale = create_sale_record(data={"item": item, "sale_date": date(2026, 2, 1), "sale_price": Decimal("100"), "quantity": 1, "actual_fees_total": 0})
    with fee_writes(), pytest.raises(ValidationError):
        FeeAdjustment.objects.create(snapshot=sale.fee_snapshot, amount=1, reason="authorization=private", provenance="human_correction")
    bad = payload(); bad["periods"][0]["rates"][0]["price"] = "123"
    with pytest.raises(ValueError):
        engine.create_version(bad)
    assert "requests" not in inspect.getsource(engine)


def test_transient_preview_and_authenticated_calendar_api(django_user_model):
    user = django_user_model.objects.create_user(username="fees")
    client = APIClient(); client.force_authenticate(user=user)
    assert client.get("/api/fee-engine/").data["state"] == "schedule unknown"
    saved = client.post("/api/fee-engine/", payload(), format="json")
    assert saved.status_code == 201, saved.data
    before = (FeeOrderSnapshot.objects.count(), SaleFeeSnapshot.objects.count(), SaleRecord.objects.count())
    result = client.post("/api/fee-engine/calculate/", {"sale_date": "2026-02-01", "destination_country": "AU", "lines": [{"key": "sample", "quantity": 1, "item_total": "100", "category_slug": "coins"}]}, format="json")
    assert result.status_code == 200 and result.data["fee_total"] == "13.42"
    assert before == (FeeOrderSnapshot.objects.count(), SaleFeeSnapshot.objects.count(), SaleRecord.objects.count())


def test_pro_basic_reverse_margin_shared_case():
    from apps.profit.services import calculate_buy
    engine.create_version(payload())
    case = FIXTURE["buy_case"]
    args = {k: case[k] for k in ("expected_sell_price", "price_basis", "seller_mode", "target_type", "flat_profit_target", "roi_pct", "roi_basis", "postage", "packaging", "refurb", "asking_price")}
    result = calculate_buy(**args, setting=ProfitSetting(), fee_context={"sale_date": case["fee_date"], "category_slug": case["fee_category"], "destination_country": case["delivery_country"]})
    assert str(result.max_buy) == case["expected_max_buy"]
    assert str(result.expected_profit_at_asking) == case["expected_profit"]
    assert str(result.roi_at_asking) == case["expected_roi"]
    assert result.verdict == "BUY"


def test_complete_order_snapshot_charges_fixed_fee_once_across_sales(item):
    engine.create_version(payload())
    order = {"sale_date": "2026-02-01", "order_id": "owned-order", "destination_country": "NZ", "postage": "10.00", "marketplace_tax": "20.00",
             "lines": [{"key": k, "quantity": 1, "item_total": "100.00", "category_slug": "coins"} for k in ("a", "b")]}
    sales = [create_sale_record(data={"item": item, "sale_date": date(2026, 2, 1), "quantity": 1, "sale_price": Decimal("100"), "actual_fees_total": None,
             "channel": "ebay_au", "ebay_order_id": "owned-order", "ebay_line_item_id": k, "fee_order": order}) for k in ("a", "b")]
    assert FeeOrderSnapshot.objects.count() == 1
    assert sum(Decimal(s.fee_snapshot.components["per_order_fee"]) for s in sales) == Decimal("0.33")
    assert sum(Decimal(s.fee_snapshot.result["revenue"]) for s in sales) == Decimal("210.00")
    assert sum(Decimal(s.fee_snapshot.components["international_fee"]) for s in sales) == Decimal("2.54")


def test_sales_ledger_and_dashboard_use_same_frozen_result(item):
    from apps.dashboard.analytics import parse_filters, build_summary, build_pnl
    from apps.sales.serializers import SaleRecordSerializer
    engine.create_version(payload())
    sale = create_sale_record(data={"item": item, "sale_date": date(2026, 2, 1), "quantity": 1, "sale_price": Decimal("100"),
        "channel": "ebay_au", "actual_fees_total": None, "fee_context": {"destination_country": "AU", "postage": "10.00", "marketplace_tax": "20.00"}})
    result = sale.fee_snapshot.result
    assert result["revenue"] == "110.00" and result["fees"] == "17.35"
    assert result["realised_profit"] == "91.65"
    serialized = SaleRecordSerializer(sale).data
    assert serialized["effective_revenue"] == "110.00" and serialized["effective_fee_total"] == "17.35"
    assert serialized["net_proceeds"] == "92.65" and serialized["realised_profit"] == "91.65"
    filters = parse_filters({"range": "all"})
    summary = build_summary(filters)["tiles"]
    assert summary["gross_revenue"]["value"] == "110.00"
    assert summary["net_proceeds"]["value"] == "92.65"
    assert summary["realised_profit"]["value"] == "91.65"
    assert ledger_rows(ProfitSetting())[0]["realised_profit"] == "91.65"
    assert build_pnl(filters)["series"][0]["realised_profit"] == "91.65"
    item.acquisition_cost = 999; item.save()
    assert build_summary(filters)["tiles"]["realised_profit"]["value"] == "91.65"


def test_ebay_calendar_never_applies_to_another_channel(item):
    from apps.dashboard.analytics import build_summary, parse_filters
    engine.create_version(payload())
    sale = create_sale_record(data={"item": item, "sale_date": date(2026, 2, 1), "sale_price": Decimal("100"), "quantity": 1,
        "channel": "manual", "actual_fees_total": None, "fee_context": {"destination_country": "AU"}})
    assert sale.fee_snapshot.version_id is None and sale.realised_profit is None
    assert sale.net_proceeds is None and FeeOrderSnapshot.objects.count() == 0
    summary = build_summary(parse_filters({"range": "all"}))["tiles"]
    assert summary["realised_profit"]["excluded_count"] == 1
    assert "fees unknown" in summary["net_proceeds"]["secondary"]


def test_unconfigured_preview_is_safe_and_legacy_estimates_remain_history(item, django_user_model):
    from apps.dashboard.analytics import build_estimate_vs_actual, parse_filters
    client = APIClient(); client.force_authenticate(user=django_user_model.objects.create_user(username="fee-preview"))
    assert client.get("/api/profit/fees/preview/", {"seller_price": "100", "seller_mode": "pro_other"}).status_code == 400
    SaleRecord.objects.create(item=item, sale_date=date(2025, 6, 1), quantity=1, sale_price=1, actual_fees_total=Decimal("0.46"),
        valuation_snapshot={"current_report": {"suggested_price": "1.00"}}, estimated_fee_snapshot={"estimated_fees_total": "0.52"})
    history = build_estimate_vs_actual(parse_filters({"range": "all"}))["fees"]
    assert history["sample_size"] == 1 and history["estimated_fees_total"] == "0.52" and history["actual_fees_total"] == "0.46"


def test_concurrent_calendars_cannot_fork_file_sqlite_and_postgres(concurrent_draft, settings, tmp_path):
    assert Path(settings.MEDIA_ROOT).is_relative_to(tmp_path)
    using = concurrent_draft._state.db
    barrier = Barrier(2)
    def worker(_):
        try:
            barrier.wait(timeout=10)
            return engine.create_version(payload(), using=using).pk
        except (ValueError, ValidationError, DatabaseError):
            return None
        finally:
            connections[using].close()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(worker, range(2)))
    assert sum(r is not None for r in results) == 1
    assert FeeScheduleVersion.objects.using(using).count() == 1
    assert FeePlanPeriod.objects.using(using).count() == 1


def test_owned_order_projection_uses_delivery_not_buyer_or_forwarding_country(item):
    from apps.ebay.order_sync import normalize_order
    raw = {"orderId": "fixture-order", "creationDate": "2026-02-01T00:00:00Z", "buyer": {"taxAddress": {"countryCode": "AU"}},
           "pricingSummary": {"deliveryCost": {"value": "10.00", "currency": "AUD"}, "tax": {"value": "0.00", "currency": "AUD"}},
           "fulfillmentStartInstructions": [{"ebaySupportedFulfillment": True, "finalDestinationAddress": {"countryCode": "NZ"}, "shippingStep": {"shipTo": {"contactAddress": {"countryCode": "AU"}}}}],
           "lineItems": [{"lineItemId": "a", "sku": item.sku, "quantity": 2, "lineItemCost": {"value": "100.00", "currency": "AUD"}}]}
    result = engine.fee_order_from_owned(normalize_order(raw)[0])
    assert result["destination_country"] == "NZ" and result["postage"] == "10.00"
    assert not any(k in json.dumps(result) for k in ("taxAddress", "contactAddress", "buyer"))
    del raw["pricingSummary"]["tax"]
    assert engine.fee_order_from_owned(normalize_order(raw)[0]) is None
