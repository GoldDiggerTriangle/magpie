from __future__ import annotations

import inspect
import json
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from rest_framework.test import APIClient

from apps.catalog.models import ProductCategory
from apps.inventory.models import InventoryItem
from apps.profit.models import ProfitSetting
from apps.profit.services import (
    PriceBasis,
    buyer_protection_fee,
    buyer_visible_total,
    calculate_buy,
    seller_price_from_buyer_visible,
)
from apps.research.models import Comparable
from apps.sales.models import SaleRecord
from apps.sales.services import create_sale_record
from django.utils import timezone


pytestmark = pytest.mark.django_db


@pytest.fixture
def user(django_user_model):
    return django_user_model.objects.create_user(username="sprint19", password="pass")


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
        maybe_band_pct=Decimal("10.000"),
    )


@pytest.fixture
def category():
    return ProductCategory.objects.create(
        name="Sprint 19 Coins",
        slug="sprint-19-coins",
        sku_prefix="S19",
        profile_key="coins",
    )


def make_item(category, *, title, year=1937, denomination="Crown"):
    return InventoryItem.objects.create(
        title=title,
        category=category,
        condition=InventoryItem.Condition.GOOD,
        quantity_total=1,
        acquisition_cost=Decimal("20.00"),
        attributes={"year": year, "denomination": denomination},
    )


def sell(item, *, amount, days_old=10):
    return create_sale_record(
        data={
            "item": item,
            "sale_date": timezone.localdate() - timedelta(days=days_old),
            "quantity": 1,
            "sale_price": Decimal(amount),
            "channel": SaleRecord.Channel.MANUAL,
            "actual_fees_total": Decimal("0.00"),
            "actual_shipping_cost": Decimal("0.00"),
        }
    )


def lookup(api_client, category, terms="1937 Crown"):
    return api_client.get(
        "/api/evidence/lookup/",
        {"category": str(category.id), "terms": terms, "attr_year": "1937", "attr_denomination": "Crown"},
    )


def test_descriptor_lookup_ranks_exact_sales_then_similar_sales_then_approved_comps(api_client, category):
    exact_item = make_item(category, title="1937 Australian Crown")
    similar_item = make_item(category, title="Australian florin", year=1938, denomination="Florin")
    sell(exact_item, amount="75.00")
    sell(similar_item, amount="42.00")
    Comparable.objects.create(
        descriptor_category=category,
        descriptor_terms=["1937", "crown"],
        descriptor_attributes={"year": 1937, "denomination": "Crown"},
        kind=Comparable.Kind.SOLD,
        source="Manual comp",
        title="1937 Crown captured comp",
        price=Decimal("70.00"),
        price_basis=Comparable.PriceBasis.SELLER_RECEIVES,
        match_scope=Comparable.MatchScope.EXACT,
    )

    response = lookup(api_client, category)

    assert response.status_code == 200, response.data
    rows = response.data["rows"]
    assert [row["source"] for row in rows[:3]] == [
        "own_sale_exact",
        "own_sale_similar",
        "approved_comp",
    ]
    assert rows[0]["match_reason"].startswith("same category")
    assert "matched terms" in rows[0]["match_reason"]


def test_descriptor_lookup_stats_use_known_seller_receives_only_and_label_uncertain_basis(api_client, category):
    for amount, days_old in [("70.00", 10), ("80.00", 40), ("90.00", 80)]:
        item = make_item(category, title="1937 Australian Crown")
        sell(item, amount=amount, days_old=days_old)
    Comparable.objects.create(
        descriptor_category=category,
        descriptor_terms=["1937", "crown"],
        kind=Comparable.Kind.SOLD,
        source="Unknown basis capture",
        title="Unknown basis high outlier",
        price=Decimal("999.00"),
        price_basis=Comparable.PriceBasis.UNKNOWN,
        match_scope=Comparable.MatchScope.EXACT,
    )

    response = lookup(api_client, category)

    assert response.status_code == 200, response.data
    assert response.data["stats"]["count"] == 3
    assert response.data["stats"]["low"] == "70.00"
    assert response.data["stats"]["median"] == "80.00"
    assert response.data["stats"]["high"] == "90.00"
    assert response.data["stats"]["unknown_basis_count"] == 1
    assert response.data["strength"]["label"] == "STRONG"
    uncertain = [row for row in response.data["rows"] if row["basis_uncertain"]]
    assert uncertain[0]["seller_receives"] is None
    assert uncertain[0]["basis_label"] == "Basis uncertain"


def test_fast_capture_v2_creates_approved_comparable_and_returns_refreshed_lookup(api_client, category):
    response = api_client.post(
        "/api/evidence/capture/",
        {
            "category": str(category.id),
            "terms": "1937 Crown",
            "attributes": {"year": 1937, "denomination": "Crown"},
            "price": "64.00",
            "price_basis": Comparable.PriceBasis.UNKNOWN,
            "source": "eBay sold result read by user",
            "source_tag": "ebay_sold",
            "title": "Captured 1937 Crown sold comp",
            "observed_on": "2026-06-20",
            "url": "https://www.ebay.com.au/itm/example",
            "notes": "Captured manually from open lookup.",
        },
        format="json",
    )

    assert response.status_code == 201, response.data
    comp = Comparable.objects.get(pk=response.data["comparable"]["id"])
    assert comp.item_id is None
    assert comp.kind == Comparable.Kind.SOLD
    assert comp.price_basis == Comparable.PriceBasis.UNKNOWN
    assert comp.descriptor_category_id == category.id
    assert response.data["lookup"]["stats"]["unknown_basis_count"] == 1
    assert response.data["lookup"]["rows"][0]["label"] == "Captured 1937 Crown sold comp"


def test_bought_it_creates_item_with_calculator_context_without_evidence_side_effects(api_client, setting, category):
    response = api_client.post(
        "/api/buy-calculator/bought-it/",
        {
            "agreed_price": "60.00",
            "expected_sell_price": "100.00",
            "price_basis": PriceBasis.SELLER_RECEIVES,
            "category": str(category.id),
            "terms": "1937 Crown",
            "attributes": {"year": 1937, "denomination": "Crown"},
            "postage": "0.00",
            "packaging": "0.00",
            "refurb": "0.00",
        },
        format="json",
    )

    assert response.status_code == 201, response.data
    item = InventoryItem.objects.get(pk=response.data["id"])
    assert item.acquisition_cost == Decimal("60.00")
    assert item.category_id == category.id
    assert item.attributes["year"] == 1937
    assert "Created from Buy Calculator" in item.notes
    assert Comparable.objects.count() == 0
    assert SaleRecord.objects.count() == 0


def test_lookup_and_what_if_calculation_do_not_persist_history_or_evidence(api_client, setting, category):
    before_items = InventoryItem.objects.count()
    before_comps = Comparable.objects.count()

    response = lookup(api_client, category)
    assert response.status_code == 200, response.data

    calc = api_client.post(
        "/api/buy-calculator/calculate/",
        {
            "expected_sell_price": "100.00",
            "price_basis": PriceBasis.SELLER_RECEIVES,
            "target_type": "roi",
            "roi_pct": "30",
            "roi_basis": ProfitSetting.RoiBasis.ALL_IN_CASH,
            "postage": "0.00",
            "packaging": "0.00",
            "refurb": "0.00",
            "asking_price": "60.00",
            "evidence_source": "what_if",
            "confidence_label": "what-if (your estimate)",
        },
        format="json",
    )
    assert calc.status_code == 200, calc.data
    assert InventoryItem.objects.count() == before_items
    assert Comparable.objects.count() == before_comps
    assert SaleRecord.objects.count() == 0


def test_shared_formula_parity_fixture_matches_backend_math(setting):
    fixture = parity_fixture()
    for case in fixture["buy_cases"]:
        result = calculate_buy(
            expected_sell_price=case["expected_sell_price"],
            price_basis=case["price_basis"],
            seller_mode=case["seller_mode"],
            setting=setting,
            target_type=case["target_type"],
            flat_profit_target=case["flat_profit_target"],
            roi_pct=case["roi_pct"],
            roi_basis=case["roi_basis"],
            postage=case["postage"],
            packaging=case["packaging"],
            refurb=case["refurb"],
            asking_price=case["asking_price"],
        )
        expected = case["expected"]
        assert str(result.max_buy) == expected["max_buy"]
        assert result.verdict == expected["verdict"]
        assert str(result.expected_profit_at_asking) == expected["expected_profit_at_asking"]
        assert str(result.roi_at_asking) == expected["roi_at_asking"]
        assert str(result.seller_fees) == expected["seller_fees"]
        assert str(result.non_buy_costs) == expected["non_buy_costs"]

    for case in fixture["bpf_round_trips"]:
        assert str(buyer_protection_fee(case["seller_receives"])) == case["buyer_protection_fee"]
        assert str(buyer_visible_total(case["seller_receives"])) == case["buyer_visible_total"]
        assert str(seller_price_from_buyer_visible(case["buyer_visible_total"])) == case["seller_receives"]


def test_descriptor_evidence_path_has_no_external_network_calls():
    import apps.research.descriptor_lookup as descriptor_lookup

    source = inspect.getsource(descriptor_lookup)
    forbidden = ["requests", "httpx", "urlopen", "urllib.request", "ebay_sdk", "openai"]
    for token in forbidden:
        assert token not in source


def parity_fixture():
    root = Path(__file__).resolve().parents[4]
    path = root / "frontend" / "src" / "fixtures" / "sprint19FormulaParity.json"
    return json.loads(path.read_text(encoding="utf-8"))
