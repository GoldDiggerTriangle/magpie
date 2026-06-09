from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.catalog.models import ProductCategory
from apps.inventory.models import InventoryItem
from apps.research.links import research_links
from apps.research.models import Comparable, ResearchRecord


@pytest.fixture
def user(django_user_model):
    return django_user_model.objects.create_user(username="researcher", password="pass")


@pytest.fixture
def api_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def item():
    category = ProductCategory.objects.create(name="Phones", slug="phones", sku_prefix="PH")
    return InventoryItem.objects.create(
        title="Example handset",
        category=category,
        attributes={"brand": "Nokia", "model": "3310"},
    )


@pytest.mark.django_db
def test_comparable_research_record_and_link_templates(item):
    comp = Comparable.objects.create(
        item=item,
        kind=Comparable.Kind.SOLD,
        source="Manual note",
        title="Sold handset",
        price=Decimal("45.00"),
    )
    record = ResearchRecord.objects.create(
        item=item,
        source="Google",
        content="Checked exact title.",
        links=[{"label": "Search", "url": "https://www.google.com/search?q=handset"}],
    )

    links = research_links(item)
    labels = {link["label"] for link in links}

    assert comp.price == Decimal("45.00")
    assert record.links[0]["label"] == "Search"
    assert {
        "eBay active",
        "eBay sold",
        "Terapeak",
        "Google",
        "Google Images",
        "Exact title",
        "Brand/model sold",
    } <= labels
    assert all(link["url"].startswith("https://") for link in links)


@pytest.mark.django_db
def test_comparable_and_research_record_api_crud(api_client, item):
    comp_create = api_client.post(
        "/api/comparables/",
        {
            "item": str(item.id),
            "kind": Comparable.Kind.SOLD,
            "source": "Manual Terapeak note",
            "title": "Comparable title",
            "price": "52.00",
            "shipping": "7.50",
            "currency": "AUD",
        },
        format="json",
    )
    assert comp_create.status_code == 201, comp_create.data

    comp_id = comp_create.data["id"]
    comp_list = api_client.get("/api/comparables/", {"item": str(item.id), "kind": "sold"})
    assert comp_list.status_code == 200
    assert comp_list.data["count"] == 1

    comp_patch = api_client.patch(
        f"/api/comparables/{comp_id}/",
        {"notes": "human checked"},
        format="json",
    )
    assert comp_patch.status_code == 200
    assert comp_patch.data["notes"] == "human checked"

    record_create = api_client.post(
        "/api/research-records/",
        {
            "item": str(item.id),
            "source": "Google",
            "content": "Looked for model variants.",
            "links": [{"label": "Google", "url": "https://www.google.com/search?q=nokia"}],
        },
        format="json",
    )
    assert record_create.status_code == 201, record_create.data
    record_id = record_create.data["id"]

    record_patch = api_client.patch(
        f"/api/research-records/{record_id}/",
        {"content": "Updated note."},
        format="json",
    )
    assert record_patch.status_code == 200
    assert record_patch.data["content"] == "Updated note."

    assert api_client.delete(f"/api/research-records/{record_id}/").status_code == 204
    assert api_client.delete(f"/api/comparables/{comp_id}/").status_code == 204


@pytest.mark.django_db
def test_unauthenticated_research_api_rejected(item):
    client = APIClient()
    response = client.get("/api/comparables/")
    assert response.status_code in {401, 403}

