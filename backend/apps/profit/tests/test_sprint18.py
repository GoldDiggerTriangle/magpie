from datetime import date
from decimal import Decimal

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
    fees_for_seller_receives,
    max_buy_for_roi_all_in_cash,
    max_buy_for_roi_on_buy_price,
    normalize_to_seller_receives,
    seller_price_from_buyer_visible,
)
from apps.research.models import Comparable
from apps.sales.models import SaleRecord
from apps.sales.services import create_sale_record


pytestmark = pytest.mark.django_db


@pytest.fixture
def user(django_user_model):
    return django_user_model.objects.create_user(username="sprint18", password="pass")


@pytest.fixture
def api_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def setting():
    return ProfitSetting.objects.create(
        seller_mode=ProfitSetting.SellerMode.FREE_SELLING,
        default_roi_pct=Decimal("25.000"),
        maybe_band_pct=Decimal("10.000"),
    )


@pytest.fixture
def category():
    return ProductCategory.objects.create(
        name="Sprint 18 Coins",
        slug="sprint-18-coins",
        sku_prefix="S18",
        profile_key="coins",
    )


@pytest.fixture
def item(category):
    return InventoryItem.objects.create(
        title="1937 Australian Crown",
        category=category,
        condition=InventoryItem.Condition.GOOD,
        quantity_total=5,
        acquisition_cost=Decimal("100.00"),
        attributes={"year": 1937, "denomination": "Crown", "grade": "VF"},
    )


@pytest.mark.parametrize(
    ("seller_price", "bpf", "buyer_total"),
    [
        ("20.00", "1.90", "21.90"),
        ("500.00", "30.70", "530.70"),
        ("5000.00", "210.70", "5210.70"),
        ("6000.00", "210.70", "6210.70"),
    ],
)
def test_buyer_protection_fee_breakpoints_and_cap(seller_price, bpf, buyer_total):
    assert buyer_protection_fee(seller_price) == Decimal(bpf)
    assert buyer_visible_total(seller_price) == Decimal(buyer_total)


@pytest.mark.parametrize("seller_price", ["12.34", "20.00", "25.50", "500.00", "501.00", "5000.00", "6000.00"])
def test_buyer_visible_inverse_round_trips_exactly(seller_price):
    buyer_total = buyer_visible_total(seller_price)
    assert seller_price_from_buyer_visible(buyer_total) == Decimal(seller_price)


def test_normalisation_converts_known_buyer_visible_and_flags_unknown():
    converted = normalize_to_seller_receives("530.70", PriceBasis.BUYER_VISIBLE)
    assert converted.seller_receives == Decimal("500.00")
    assert converted.basis_uncertain is False

    unknown = normalize_to_seller_receives("530.70", PriceBasis.UNKNOWN)
    assert unknown.seller_receives is None
    assert unknown.basis_uncertain is True


def test_fee_modes_model_free_selling_and_pro_starter(setting):
    free = fees_for_seller_receives(
        seller_receives="100.00",
        seller_mode=ProfitSetting.SellerMode.FREE_SELLING,
        setting=setting,
    )
    assert free.total_seller_fees == Decimal("0.00")
    assert free.buyer_protection_fee == Decimal("6.70")
    assert free.buyer_visible_total == Decimal("106.70")

    pro = fees_for_seller_receives(
        seller_receives="100.00",
        seller_mode=ProfitSetting.SellerMode.PRO_STARTER,
        setting=setting,
    )
    assert pro.total_seller_fees == Decimal("13.40")
    assert pro.buyer_protection_fee == Decimal("0.00")


def test_roi_formulas_and_zero_cost_equivalence():
    assert max_buy_for_roi_all_in_cash(
        seller_receives="100.00",
        seller_fees="0.00",
        non_buy_costs="20.00",
        roi_pct="25",
    ) == Decimal("60.00")
    assert max_buy_for_roi_on_buy_price(
        net_proceeds_before_buy="80.00",
        roi_pct="25",
    ) == Decimal("64.00")
    assert max_buy_for_roi_all_in_cash(
        seller_receives="100.00",
        seller_fees="0.00",
        non_buy_costs="0.00",
        roi_pct="25",
    ) == max_buy_for_roi_on_buy_price(
        net_proceeds_before_buy="100.00",
        roi_pct="25",
    )


def test_buy_verdicts_use_configured_maybe_band(setting):
    result = calculate_buy(
        expected_sell_price="100.00",
        price_basis=PriceBasis.SELLER_RECEIVES,
        seller_mode=setting.seller_mode,
        setting=setting,
        target_type="flat",
        flat_profit_target="25.00",
        roi_pct="25",
        roi_basis=ProfitSetting.RoiBasis.ALL_IN_CASH,
        postage="5.00",
        packaging="5.00",
        refurb="0.00",
        asking_price="65.00",
    )
    assert result.max_buy == Decimal("65.00")
    assert result.verdict == "BUY"

    maybe = calculate_buy(
        expected_sell_price="100.00",
        price_basis=PriceBasis.SELLER_RECEIVES,
        seller_mode=setting.seller_mode,
        setting=setting,
        target_type="flat",
        flat_profit_target="25.00",
        roi_pct="25",
        roi_basis=ProfitSetting.RoiBasis.ALL_IN_CASH,
        postage="5.00",
        packaging="5.00",
        refurb="0.00",
        asking_price="70.00",
    )
    assert maybe.verdict == "MAYBE"

    passed = calculate_buy(
        expected_sell_price="100.00",
        price_basis=PriceBasis.SELLER_RECEIVES,
        seller_mode=setting.seller_mode,
        setting=setting,
        target_type="flat",
        flat_profit_target="25.00",
        roi_pct="25",
        roi_basis=ProfitSetting.RoiBasis.ALL_IN_CASH,
        postage="5.00",
        packaging="5.00",
        refurb="0.00",
        asking_price="80.00",
    )
    assert passed.verdict == "PASS"


@pytest.mark.django_db
def test_calculator_what_if_does_not_persist_evidence(api_client, setting):
    response = api_client.post(
        "/api/buy-calculator/calculate/",
        {
            "expected_sell_price": "100.00",
            "price_basis": PriceBasis.SELLER_RECEIVES,
            "target_type": "roi",
            "roi_pct": "25",
            "roi_basis": ProfitSetting.RoiBasis.ALL_IN_CASH,
            "postage": "0.00",
            "packaging": "0.00",
            "refurb": "0.00",
            "asking_price": "70.00",
            "evidence_source": "what_if",
            "confidence_label": "what-if (your estimate)",
        },
        format="json",
    )

    assert response.status_code == 200, response.data
    assert response.data["confidence_label"] == "what-if (your estimate)"
    assert Comparable.objects.count() == 0
    assert SaleRecord.objects.count() == 0


@pytest.mark.django_db
def test_evidence_lookup_prefers_exact_own_sales_and_does_not_use_unknown_basis_comp(api_client, setting, item):
    create_sale_record(
        data={
            "item": item,
            "sale_date": date(2026, 6, 20),
            "quantity": 1,
            "sale_price": Decimal("75.00"),
            "channel": SaleRecord.Channel.MANUAL,
            "actual_fees_total": Decimal("0.00"),
            "actual_shipping_cost": Decimal("0.00"),
        }
    )
    Comparable.objects.create(
        item=item,
        kind=Comparable.Kind.SOLD,
        source="eBay manual capture",
        title="Buyer-visible uncertain comp",
        price=Decimal("999.00"),
        price_basis=Comparable.PriceBasis.UNKNOWN,
        match_scope=Comparable.MatchScope.EXACT,
    )

    response = api_client.get(f"/api/buy-calculator/evidence/?item={item.id}")

    assert response.status_code == 200, response.data
    assert response.data["suggested"]["price"] == "75.00"
    assert response.data["suggested"]["confidence_label"] == "own sale - exact"
    uncertain = [row for row in response.data["evidence"] if row["basis_uncertain"]]
    assert uncertain
    assert uncertain[0]["seller_receives"] is None
