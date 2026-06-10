from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.catalog.models import ProductCategory
from apps.catalog.profiles import (
    CoinSchema,
    PhoneSchema,
    StampSchema,
    get_schema,
)
from apps.inventory.models import InventoryItem
from apps.research.links import URL_TEMPLATES_VERIFIED, research_links
from apps.valuation.models import ValuationReport


@pytest.fixture
def user(django_user_model):
    return django_user_model.objects.create_user(username="sprint4", password="pass")


@pytest.fixture
def api_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def categories():
    return {
        "stamps": ProductCategory.objects.create(
            name="Stamps",
            slug="stamps-sprint4",
            sku_prefix="STM",
            profile_key="stamps",
        ),
        "coins": ProductCategory.objects.create(
            name="Coins",
            slug="coins-sprint4",
            sku_prefix="COIN",
            profile_key="coins",
        ),
        "phones": ProductCategory.objects.create(
            name="Phones & Electronics",
            slug="phones-sprint4",
            sku_prefix="PH",
            profile_key="phones",
        ),
        "gold": ProductCategory.objects.create(
            name="Gold",
            slug="gold-sprint4",
            sku_prefix="GOLD",
            profile_key="gold",
        ),
        "tools": ProductCategory.objects.create(
            name="Tools",
            slug="tools-sprint4",
            sku_prefix="TOOL",
            profile_key="",
        ),
    }


def test_sprint4_schemas_partial_capture_valid_values_and_rejections():
    stamp = StampSchema()
    assert stamp.validate({}) == {}
    assert stamp.validate(
        {
            "country": "Australia",
            "year": "1932",
            "denomination": "2d",
            "catalogue_refs": [{"system": "SG", "number": "144"}],
            "mint_used": "used",
        }
    ) == {
        "country": "Australia",
        "year": 1932,
        "denomination": "2d",
        "catalogue_refs": [{"system": "SG", "number": "144"}],
        "mint_used": "used",
    }
    with pytest.raises(ValueError, match="year"):
        stamp.validate({"year": 1839})
    with pytest.raises(ValueError, match="mint_used"):
        stamp.validate({"mint_used": "mint"})
    with pytest.raises(ValueError, match="catalogue_refs"):
        stamp.validate({"catalogue_refs": [{"system": "SG"}]})
    with pytest.raises(ValueError, match="Unknown"):
        stamp.validate({"stamp_extra": "VF"})

    coin = CoinSchema()
    assert coin.validate({}) == {}
    assert coin.validate(
        {
            "country": "Australia",
            "year": "1937",
            "denomination": "Crown",
            "mintage": "1008000",
            "catalogue_refs": [{"system": "KM", "number": "34"}],
            "cert": {"grader": "PCGS", "cert_no": "12345678"},
            "weight_g": "7.988",
            "fineness": "0.9167",
        }
    )["cert"] == {"grader": "PCGS", "cert_no": "12345678"}
    with pytest.raises(ValueError, match="fineness"):
        coin.validate({"fineness": "0"})
    with pytest.raises(ValueError, match="mintage"):
        coin.validate({"mintage": "-1"})
    with pytest.raises(ValueError, match="cert.cert_no"):
        coin.validate({"cert": {"grader": "NGC"}})
    with pytest.raises(ValueError, match="Unknown"):
        coin.validate({"coin_extra": "MS64"})

    phone = PhoneSchema()
    assert phone.validate({"imei": "not-luhn-this-sprint"}) == {"imei": "not-luhn-this-sprint"}
    assert phone.validate({"storage_gb": "128", "battery_health_pct": "87"}) == {
        "storage_gb": 128,
        "battery_health_pct": 87,
    }
    with pytest.raises(ValueError, match="battery_health_pct"):
        phone.validate({"battery_health_pct": 101})
    with pytest.raises(ValueError, match="network_status"):
        phone.validate({"network_status": "locked"})
    with pytest.raises(ValueError, match="Unknown"):
        phone.validate({"phone_extra": "good"})


@pytest.mark.django_db
def test_schema_endpoint_returns_descriptors(api_client, categories):
    for key in ("stamps", "coins", "phones", "gold"):
        response = api_client.get(f"/api/categories/{categories[key].id}/schema/")
        assert response.status_code == 200, response.data
        assert response.data["profile_key"] == key
        names = {field["name"] for field in response.data["fields"]}
        assert names
        assert all(field["required"] is False for field in response.data["fields"])

    coin_response = api_client.get(f"/api/categories/{categories['coins'].id}/schema/")
    fields = {field["name"]: field for field in coin_response.data["fields"]}
    assert fields["catalogue_refs"]["type"] == "list[object]"
    assert fields["cert"]["type"] == "object"
    assert fields["weight_g"]["type"] == "decimal"
    assert "grade" in fields

    permissive = api_client.get(f"/api/categories/{categories['tools'].id}/schema/")
    assert permissive.status_code == 200
    assert permissive.data == {"profile_key": "", "fields": []}


@pytest.mark.django_db
def test_item_api_partial_capture_unknown_keys_and_grandfather_next_write(api_client, categories):
    stamp_response = api_client.post(
        "/api/items/",
        {
            "title": "Partial stamp",
            "category": str(categories["stamps"].id),
            "condition": "ungraded",
            "location": None,
            "estimated_value": None,
            "notes": "",
            "attributes": {},
        },
        format="json",
    )
    assert stamp_response.status_code == 201, stamp_response.data
    assert stamp_response.data["attributes"] == {}

    bad_response = api_client.post(
        "/api/items/",
        {
            "title": "Bad stamp",
            "category": str(categories["stamps"].id),
            "condition": "ungraded",
            "location": None,
            "estimated_value": None,
            "notes": "",
            "attributes": {"lot_type": "mixed"},
        },
        format="json",
    )
    assert bad_response.status_code == 400
    assert "attributes" in bad_response.data

    legacy = InventoryItem.objects.create(
        title="Legacy stamp",
        category=categories["stamps"],
        attributes={},
    )
    InventoryItem.objects.filter(pk=legacy.pk).update(attributes={"lot_type": "mixed"})
    legacy.refresh_from_db()
    assert legacy.attributes == {"lot_type": "mixed"}

    next_write = api_client.patch(
        f"/api/items/{legacy.id}/",
        {"notes": "next write validates"},
        format="json",
    )
    assert next_write.status_code == 400
    assert "attributes" in next_write.data


@pytest.mark.django_db
def test_research_links_are_category_aware_and_payloads_are_extended(categories):
    assert URL_TEMPLATES_VERIFIED is True

    stamp = InventoryItem.objects.create(
        title="Harbour Bridge stamp",
        category=categories["stamps"],
        attributes={"country": "Australia", "year": 1932, "denomination": "2d"},
    )
    stamp_links = research_links(stamp)
    sg = next(link for link in stamp_links if "Stanley Gibbons" in link["label"])
    assert sg["type"] == "link"
    assert sg["source"] == "dealer asking (shop search) - not catalogue value"
    assert "catalogue value" in sg["note"]

    coin = InventoryItem.objects.create(
        title="1937 Crown",
        category=categories["coins"],
        attributes={
            "country": "Australia",
            "year": 1937,
            "denomination": "Crown",
            "cert": {"grader": "PCGS", "cert_no": "12345678"},
        },
    )
    coin_links = research_links(coin)
    labels = {entry["label"] for entry in coin_links}
    assert {"Numista", "Colnect coins", "PCGS cert verification"} <= labels
    renniks = next(entry for entry in coin_links if "Renniks" in entry["label"])
    assert renniks["type"] == "checklist"
    assert renniks["url"] is None
    assert renniks["source"] == "manual checklist"
    assert "NGC cert verification" not in labels

    phone = InventoryItem.objects.create(
        title="Fallback handset",
        category=categories["phones"],
        attributes={},
    )
    phone_links = research_links(phone)
    gsmarena = next(entry for entry in phone_links if entry["label"] == "GSMArena")
    assert "Fallback+handset" in gsmarena["url"]
    assert gsmarena["source"] == "spec database"

    for entry in stamp_links + coin_links + phone_links:
        assert set(entry) == {"type", "label", "url", "note", "source"}
        assert entry["type"] in {"link", "checklist"}
        assert entry["source"]
        if entry["type"] == "link":
            assert entry["url"].startswith("https://")
        else:
            assert entry["url"] is None


@pytest.mark.django_db
def test_generic_sprint2_research_links_still_work(categories):
    item = InventoryItem.objects.create(
        title="Generic tool",
        category=categories["tools"],
        attributes={"anything": True},
    )
    links = research_links(item)
    labels = {entry["label"] for entry in links}
    assert {
        "eBay active",
        "eBay sold",
        "Terapeak",
        "Google",
        "Google Images",
        "Exact title",
        "Brand/model sold",
    } <= labels
    assert all(entry["type"] == "link" for entry in links)


@pytest.mark.django_db
def test_bullion_coin_uses_existing_commodity_valuation_strategies(api_client, settings, categories):
    settings.METALS_PROVIDER = "fake"
    item = InventoryItem.objects.create(
        title="Bullion sovereign",
        category=categories["coins"],
        attributes={
            "denomination": "Sovereign",
            "weight_g": "7.988",
            "fineness": "0.9167",
        },
    )

    manual = api_client.post(
        f"/api/items/{item.id}/valuation-reports/",
        {
            "strategy": ValuationReport.Strategy.COMMODITY_MANUAL,
            "inputs": {
                "metal": "gold",
                "weight_g": "7.988",
                "fineness": "0.9167",
                "spot_price_per_g": "100",
            },
        },
        format="json",
    )
    assert manual.status_code == 201, manual.data
    assert Decimal(manual.data["estimate_median"]) == Decimal("732.26")

    live = api_client.post(
        f"/api/items/{item.id}/valuation-reports/",
        {
            "strategy": ValuationReport.Strategy.COMMODITY_LIVE,
            "inputs": {
                "metal": "gold",
                "currency": "AUD",
                "weight_g": "7.988",
                "fineness": "0.9167",
            },
        },
        format="json",
    )
    assert live.status_code == 201, live.data
    assert live.data["inputs"]["source"] == "fake"

    missing_weight = api_client.post(
        f"/api/items/{item.id}/valuation-reports/",
        {
            "strategy": ValuationReport.Strategy.COMMODITY_LIVE,
            "inputs": {"metal": "gold", "fineness": "0.9167"},
        },
        format="json",
    )
    assert missing_weight.status_code == 422
    assert "inputs" in missing_weight.data


def test_registered_schemas_include_sprint4_profiles():
    assert get_schema("stamps").profile_key == "stamps"
    assert get_schema("coins").profile_key == "coins"
    assert get_schema("phones").profile_key == "phones"
    assert get_schema("").fields() == []
