from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.catalog.models import ProductCategory
from apps.inventory.models import InventoryItem
from apps.research.comparable_capture import comparable_capture_draft
from apps.research.models import Comparable


@pytest.fixture
def user(django_user_model):
    return django_user_model.objects.create_user(username="comparable-capture", password="pass")


@pytest.fixture
def api_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def banknote_category():
    return ProductCategory.objects.create(
        name="Banknotes",
        slug="capture-banknotes",
        sku_prefix="BN",
        profile_key="banknotes",
    )


@pytest.fixture
def banknote(banknote_category):
    return InventoryItem.objects.create(
        title="Bank of Canada one dollar note",
        category=banknote_category,
        condition=InventoryItem.Condition.UNGRADED,
        acquisition_cost=Decimal("2.00"),
        attributes={"country": "Canada", "denomination": "$1"},
    )


def test_ebay_sold_screenshot_text_prefills_comparable_draft():
    text = """
    SOLD 14 JUN 2026
    1954 *M/Y ASTERISK $1.00 BC-37bA * SCARCE Elizabeth II Bank of Cana...
    AU $11.13
    or Best Offer
    +AU $24.29 delivery from Canada
    Sell one like this
    """

    result = comparable_capture_draft(url="https://ebay.io/m/gPzKet", ocr_text=text)

    assert result.available is True
    assert result.draft["source"] == "eBay sold"
    assert result.draft["source_tag"] == "ebay_sold"
    assert result.draft["url"] == "https://ebay.io/m/gPzKet"
    assert result.draft["title"].startswith("1954 *M/Y ASTERISK $1.00 BC-37bA")
    assert result.draft["price"] == "11.13"
    assert result.draft["price_basis"] == Comparable.PriceBasis.BUYER_VISIBLE
    assert result.draft["shipping"] == "24.29"
    assert result.draft["observed_on"] == "2026-06-14"
    assert result.draft["sale_format"] == Comparable.SaleFormat.FIXED_PRICE
    assert "screenshot" in result.parsed_from


def test_link_only_records_source_without_fetching_or_inventing_price():
    result = comparable_capture_draft(url="https://ebay.io/m/gPzKet")

    assert result.available is True
    assert result.draft["source"] == "eBay sold"
    assert result.draft["source_tag"] == "ebay_sold"
    assert result.draft["url"] == "https://ebay.io/m/gPzKet"
    assert result.draft["title"] == ""
    assert result.draft["price"] == ""
    assert result.draft["price_basis"] == Comparable.PriceBasis.UNKNOWN
    assert "did not fetch" in result.detail


@pytest.mark.django_db
def test_capture_draft_endpoint_does_not_create_comparable(api_client, banknote):
    response = api_client.post(
        f"/api/items/{banknote.id}/pricing-evidence/capture-draft/",
        {"url": "https://ebay.io/m/gPzKet"},
        format="json",
    )

    assert response.status_code == 200, response.data
    assert response.data["draft"]["url"] == "https://ebay.io/m/gPzKet"
    assert response.data["draft"]["price"] == ""
    assert Comparable.objects.count() == 0


@pytest.mark.django_db
def test_capture_draft_endpoint_parses_pasted_screenshot_text(api_client, banknote):
    response = api_client.post(
        f"/api/items/{banknote.id}/pricing-evidence/capture-draft/",
        {
            "url": "https://ebay.io/m/gPzKet",
            "screenshot_text": "SOLD 14 JUN 2026 1954 *M/Y ASTERISK $1.00 BC-37bA AU $11.13 or Best Offer +AU $24.29 delivery",
        },
        format="json",
    )

    assert response.status_code == 200, response.data
    assert response.data["draft"]["price"] == "11.13"
    assert response.data["draft"]["shipping"] == "24.29"
    assert response.data["draft"]["observed_on"] == "2026-06-14"
    assert response.data["draft"]["price_basis"] == Comparable.PriceBasis.BUYER_VISIBLE
    assert Comparable.objects.count() == 0


def test_comparable_capture_parser_has_no_marketplace_fetch_imports():
    import apps.research.comparable_capture as comparable_capture

    source = comparable_capture.__loader__.get_source(comparable_capture.__name__)
    assert "requests" not in source
    assert "httpx" not in source
    assert "urlopen" not in source
