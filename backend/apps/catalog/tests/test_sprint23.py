from datetime import date
from decimal import Decimal
import json
from pathlib import Path

import pytest
from rest_framework.test import APIClient

from apps.catalog.denominations import denomination_values, load_denomination_registry
from apps.catalog.models import ProductCategory
from apps.catalog.profiles import get_schema
from apps.intelligence.ai_research import build_item_context, normalize_ai_field
from apps.intelligence.sold_search import build_sold_search_links, broad_query
from apps.inventory.models import InventoryItem
from apps.listing.copy_packs import render_copy_pack
from apps.research.descriptor_lookup import descriptor_lookup_payload
from apps.research.models import Comparable
from apps.research.pricing_sources import pricing_source_links
from apps.research.links import research_links
from apps.sales.models import SaleRecord
from apps.sales.services import create_sale_record


@pytest.fixture
def user(django_user_model):
    return django_user_model.objects.create_user(username="sprint23", password="pass")


@pytest.fixture
def api_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def banknote_category(db):
    category, _ = ProductCategory.objects.update_or_create(
        slug="banknotes",
        defaults={
            "name": "Banknotes",
            "sku_prefix": "NOTE",
            "profile_key": "banknotes",
            "description": "",
        },
    )
    return category


def make_banknote(category, *, title="Australian $10 banknote", serial="AA 123456"):
    return InventoryItem.objects.create(
        title=title,
        category=category,
        condition=InventoryItem.Condition.GOOD,
        quantity_total=2,
        acquisition_cost=Decimal("10.00"),
        target_price=Decimal("35.00"),
        attributes={
            "country": "Australia",
            "denomination": "$10",
            "series_year": "1988",
            "prefix_serial": serial,
            "signature_variety": "Johnston/Fraser",
            "catalogue_refs": [{"system": "Pick", "number": "49"}],
            "notes": "Polymer commemorative note.",
        },
    )


@pytest.mark.django_db
def test_banknotes_category_exists_from_migration():
    category = ProductCategory.objects.get(slug="banknotes")

    assert category.name == "Banknotes"
    assert category.profile_key == "banknotes"
    assert category.sku_prefix == "NOTE"


@pytest.mark.django_db
def test_banknotes_schema_and_denomination_data(api_client, banknote_category):
    InventoryItem.objects.create(
        title="Live denomination example",
        category=banknote_category,
        attributes={"country": "Australia", "denomination": "Ten shillings"},
    )

    response = api_client.get(f"/api/categories/{banknote_category.id}/schema/")

    assert response.status_code == 200, response.data
    fields = {field["name"]: field for field in response.data["fields"]}
    assert {
        "country",
        "denomination",
        "series_year",
        "prefix_serial",
        "signature_variety",
        "catalogue_refs",
        "notes",
    } <= set(fields)
    assert "$10" in fields["denomination"]["suggestions"]
    assert "Ten shillings" in fields["denomination"]["suggestions"]
    catalogue_refs = fields["catalogue_refs"]
    assert "Candidate references only" in catalogue_refs["help_text"]
    assert catalogue_refs["item_shape"]["system"]["choices"] == ["Pick", "Renniks", "McDonald", "other"]


@pytest.mark.django_db
def test_banknote_fields_persist_display_and_catalogue_refs_are_candidates(api_client, banknote_category):
    item = make_banknote(banknote_category)

    response = api_client.get(f"/api/items/{item.id}/")

    assert response.status_code == 200, response.data
    assert str(response.data["category"]) == str(banknote_category.id)
    assert response.data["attributes"]["denomination"] == "$10"
    assert response.data["attributes"]["catalogue_refs"] == [{"system": "Pick", "number": "49"}]
    field, confidence = normalize_ai_field("attributes.catalogue_refs", "high", False)
    assert field == "ai_candidate.catalogue_refs"
    assert confidence == "candidate"


@pytest.mark.django_db
def test_banknotes_flow_through_sold_search_sources_copy_pack_and_ai_scope(banknote_category):
    item = make_banknote(banknote_category)

    assert broad_query(item) == "Australia $10 1988 AA 123456 Johnston/Fraser"
    sold_links = {link.id: link for link in build_sold_search_links(item)}
    assert "broad" in sold_links
    assert "LH_Sold=1" in sold_links["broad"].url
    assert "Australia" in sold_links["broad"].query
    source_links = {link.id: link for link in pricing_source_links(item)}
    assert {"ebay_sold", "colnect_banknotes", "numista_banknotes"} <= set(source_links)
    legacy_links = {entry["label"]: entry for entry in research_links(item)}
    assert "Colnect banknotes" in legacy_links
    assert "Check Pick / Renniks banknote references" in legacy_links
    pack = render_copy_pack(item, channel="generic")
    assert "denomination: $10" in pack["sections"]["description"]
    context = build_item_context(item)
    schema_fields = {field["name"]: field for field in context["field_schema"]}
    assert context["profile_key"] == "banknotes"
    assert schema_fields["catalogue_refs"]["item_shape"]["system"]["choices"][0] == "Pick"


@pytest.mark.django_db
def test_banknotes_are_in_descriptor_evidence_lookup(banknote_category):
    item = make_banknote(banknote_category)
    create_sale_record(
        data={
            "item": item,
            "sale_date": date(2026, 7, 1),
            "quantity": 1,
            "sale_price": Decimal("44.00"),
            "channel": SaleRecord.Channel.MANUAL,
            "actual_fees_total": Decimal("0.00"),
            "actual_shipping_cost": Decimal("0.00"),
        }
    )
    Comparable.objects.create(
        item=item,
        kind=Comparable.Kind.SOLD,
        source="Manual banknote comp",
        title="Australian $10 1988 banknote sold",
        price=Decimal("40.00"),
        price_basis=Comparable.PriceBasis.SELLER_RECEIVES,
        descriptor_category=banknote_category,
        descriptor_terms=["Australia", "$10", "1988"],
        descriptor_attributes={"country": "Australia", "denomination": "$10"},
        match_scope=Comparable.MatchScope.SIMILAR,
        match_reason="same category; same denomination",
        observed_on=date(2026, 6, 20),
    )

    payload = descriptor_lookup_payload(
        category_id=str(banknote_category.id),
        terms="Australia 1988 $10",
        attributes={"country": "Australia", "denomination": "$10"},
    )

    assert payload["lookup"]["category_label"] == "Banknotes"
    assert payload["rows"][0]["source"] == "own_sale_exact"
    assert payload["rows"][0]["match_scope"] == "exact"
    assert payload["rows"][0]["seller_receives"] == "44.00"
    assert any(row["record_type"] == "comparable" for row in payload["rows"])
    assert payload["stats"]["count"] >= 2


def test_denomination_lists_are_data_config(tmp_path):
    registry_path = tmp_path / "denominations.json"
    registry_path.write_text(json.dumps({"banknotes": ["$10", "$200"]}), encoding="utf-8")

    registry = load_denomination_registry(registry_path)

    assert registry["banknotes"] == ["$10", "$200"]


def test_no_new_network_or_ai_paths_for_sprint23():
    import apps.intelligence.sold_search as sold_search
    import apps.research.links as research_links_module
    import apps.research.pricing_sources as pricing_sources

    for module in [sold_search, research_links_module, pricing_sources]:
        source = Path(module.__file__).read_text(encoding="utf-8")
        assert "requests" not in source
        assert "httpx" not in source
        assert "urlopen" not in source

    schema = get_schema("banknotes").fields()
    assert any(field["name"] == "denomination" for field in schema)
    assert denomination_values("banknotes")
