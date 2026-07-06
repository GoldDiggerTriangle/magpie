from __future__ import annotations

from decimal import Decimal
import json
from pathlib import Path

import pytest
from rest_framework.test import APIClient

from apps.catalog.models import ProductCategory
from apps.intelligence.ai_adapters import FakeAiResearchAdapter
from apps.intelligence.ai_research import build_item_context, run_identify_for_item
from apps.intelligence.identify_scope import build_identify_scope, load_identify_scope_registry
from apps.intelligence.models import FieldSuggestion
from apps.inventory.models import InventoryItem


@pytest.fixture
def user(django_user_model):
    return django_user_model.objects.create_user(username="sprint24", password="pass")


@pytest.fixture
def api_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def banknote_category(db):
    return ProductCategory.objects.create(
        name="Banknotes",
        slug="sprint24-banknotes",
        sku_prefix="N24",
        profile_key="banknotes",
    )


def make_banknote(category):
    return InventoryItem.objects.create(
        title="Australian $10 banknote",
        category=category,
        condition=InventoryItem.Condition.GOOD,
        acquisition_cost=Decimal("10.00"),
    )


def test_banknote_identify_scope_is_configured_for_full_schema():
    scope = build_identify_scope("banknotes")

    assert {
        "attributes.country",
        "attributes.denomination",
        "attributes.series_year",
        "attributes.prefix_serial",
        "attributes.signature_variety",
    } <= set(scope["fields"])
    assert "attributes.catalogue_refs" in scope["candidate_fields"]
    assert "condition" in scope["observation_fields"]
    assert {"title", "short_description"} <= set(scope["copywriting_drafts"])


def test_identify_scope_is_data_config(tmp_path):
    registry_path = tmp_path / "identify_scope.json"
    registry_path.write_text(
        json.dumps(
            {
                "banknotes": {
                    "fields": ["attributes.country", "attributes.denomination", "attributes.watermark"],
                    "candidate_fields": ["attributes.catalogue_refs"],
                    "observation_fields": ["condition"],
                    "copywriting_drafts": ["title", "short_description"],
                }
            }
        ),
        encoding="utf-8",
    )

    registry = load_identify_scope_registry(registry_path)
    scope = build_identify_scope("banknotes", registry_path=registry_path)

    assert registry["banknotes"]["fields"][-1] == "attributes.watermark"
    assert "attributes.watermark" in scope["fields"]


@pytest.mark.django_db
def test_banknotes_fake_identify_stages_full_schema_and_drafts_without_mutating(banknote_category):
    item = make_banknote(banknote_category)

    result = run_identify_for_item(item, adapter=FakeAiResearchAdapter(), storage=None)

    item.refresh_from_db()
    assert item.title == "Australian $10 banknote"
    assert item.attributes == {}
    fields = set(FieldSuggestion.objects.filter(item=item).values_list("field", flat=True))
    assert {
        "title",
        "attributes.country",
        "attributes.denomination",
        "attributes.series_year",
        "attributes.prefix_serial",
        "attributes.signature_variety",
        "ai_candidate.catalogue_refs",
        "ai_observation.condition",
        "ai_candidate.short_description_draft",
    } <= fields
    assert result["call"].request_metadata["identify_scope"]["fields"]


@pytest.mark.django_db
def test_catalogue_refs_and_condition_observations_remain_review_only(api_client, banknote_category):
    item = make_banknote(banknote_category)
    run_identify_for_item(item, adapter=FakeAiResearchAdapter(), storage=None)
    candidate = FieldSuggestion.objects.get(item=item, field="ai_candidate.catalogue_refs")
    observation = FieldSuggestion.objects.get(item=item, field="ai_observation.condition")

    candidate_response = api_client.post(f"/api/field-suggestions/{candidate.id}/approve/")
    observation_response = api_client.post(f"/api/field-suggestions/{observation.id}/approve/")

    assert candidate_response.status_code == 200, candidate_response.data
    assert observation_response.status_code == 200, observation_response.data
    item.refresh_from_db()
    assert item.attributes == {}
    assert item.condition == InventoryItem.Condition.GOOD


def test_no_new_network_paths_for_identify_scope_registry():
    import apps.intelligence.identify_scope as identify_scope

    source = Path(identify_scope.__file__).read_text(encoding="utf-8")
    assert "requests" not in source
    assert "httpx" not in source
    assert "urlopen" not in source
