from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from io import BytesIO

import pytest
from django.db import connection
from PIL import Image
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.catalog.models import ProductCategory
from apps.core.backup_ops import DB_SNAPSHOT_NAME
from apps.core.tests.backup_helpers import (
    load_backup_manifest,
    run_encrypted_backup,
    sqlite_count,
)
from apps.intelligence.ai_adapters import (
    AIReferenceQuery,
    AIResearchResult,
    AISuggestionCandidate,
    FakeAiResearchAdapter,
)
from apps.intelligence.ai_research import (
    configure_ai_credential,
    run_identify_for_item,
    run_price_assist_for_item,
    strip_exif_for_ai,
)
from apps.intelligence.models import (
    AICredential,
    AIReferenceLink,
    AIResearchCall,
    AIResearchSearchTerm,
    FieldSuggestion,
)
from apps.inventory.models import InventoryItem
from apps.photos.models import PhotoAsset
from apps.research.pricing_sources import pricing_source_links


@dataclass
class RecordingStorage:
    files: dict[str, bytes]

    def open(self, key: str) -> bytes:
        return self.files[key]


class PriceNoisyFakeAdapter(FakeAiResearchAdapter):
    def price_assist(self, *, item_context: dict) -> AIResearchResult:
        return AIResearchResult(
            suggestions=[
                AISuggestionCandidate(
                    field="estimated_value",
                    value="100",
                    confidence_band="high",
                    evidence="A prohibited price-like field from a bad provider response.",
                    source_basis="bad fake",
                )
            ],
            search_terms=[
                "1932 bridge stamp",
                "$100 bridge stamp valuation",
                "bridge stamp estimated value 100 AUD",
            ],
            reference_queries=[
                AIReferenceQuery(
                    label="Reference lookup",
                    query="1932 bridge stamp reference",
                    source_basis="bad fake",
                )
            ],
            input_tokens=10,
            output_tokens=5,
            estimated_cost_usd=Decimal("0.000010"),
        )


@pytest.fixture
def user(django_user_model):
    return django_user_model.objects.create_user(username="sprint15", password="pass")


@pytest.fixture
def api_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def stamp_category():
    return ProductCategory.objects.create(
        name="Stamps",
        slug="sprint15-stamps",
        sku_prefix="S15",
        profile_key="stamps",
    )


def image_bytes_with_exif() -> bytes:
    image = Image.new("RGB", (120, 90), "white")
    exif = Image.Exif()
    exif[0x010F] = "TestCamera"
    output = BytesIO()
    image.save(output, format="JPEG", exif=exif)
    return output.getvalue()


@pytest.mark.django_db
def test_fake_adapter_maps_structured_response_into_staged_ai_suggestions(stamp_category):
    item = InventoryItem.objects.create(
        title="Australia 1932 Harbour Bridge 2d",
        category=stamp_category,
    )
    PhotoAsset.objects.create(
        item=item,
        original_path="originals/item.jpg",
        processed_path="processed/item.jpg",
    )
    storage = RecordingStorage({"processed/item.jpg": image_bytes_with_exif()})

    result = run_identify_for_item(
        item,
        adapter=FakeAiResearchAdapter(),
        storage=storage,
    )

    item.refresh_from_db()
    assert item.title == "Australia 1932 Harbour Bridge 2d"
    assert item.attributes == {}
    assert result["call"].provider == "fake"
    assert result["call"].image_count == 1
    assert result["call"].exif_stripped is True
    assert FieldSuggestion.objects.filter(item=item, source=FieldSuggestion.Source.AI).count() == 4
    assert FieldSuggestion.objects.filter(item=item, field="ai_candidate.catalogue_id").exists()
    assert AIResearchSearchTerm.objects.filter(item=item).count() == 2
    assert AIReferenceLink.objects.filter(item=item).count() == 2


@pytest.mark.django_db
def test_ai_review_requires_explicit_approve_edit_or_reject(api_client, stamp_category):
    item = InventoryItem.objects.create(title="Review target", category=stamp_category)
    run_identify_for_item(item, adapter=FakeAiResearchAdapter(), storage=RecordingStorage({}))
    item.refresh_from_db()
    assert item.title == "Review target"
    assert item.attributes == {}

    title_suggestion = FieldSuggestion.objects.get(item=item, field="title")
    country_suggestion = FieldSuggestion.objects.get(item=item, field="attributes.country")
    year_suggestion = FieldSuggestion.objects.get(item=item, field="attributes.year")
    candidate = FieldSuggestion.objects.get(item=item, field="ai_candidate.catalogue_id")

    approved = api_client.post(f"/api/field-suggestions/{title_suggestion.id}/approve/")
    assert approved.status_code == 200, approved.data
    item.refresh_from_db()
    assert item.title.startswith("AI identified")

    edited = api_client.post(
        f"/api/field-suggestions/{country_suggestion.id}/edit/",
        {"value": "New Zealand"},
        format="json",
    )
    assert edited.status_code == 200, edited.data
    item.refresh_from_db()
    assert item.attributes["country"] == "New Zealand"

    before_reject = dict(item.attributes)
    rejected = api_client.post(f"/api/field-suggestions/{year_suggestion.id}/reject/")
    assert rejected.status_code == 200, rejected.data
    item.refresh_from_db()
    assert item.attributes == before_reject

    before_candidate = dict(item.attributes)
    candidate_response = api_client.post(f"/api/field-suggestions/{candidate.id}/approve/")
    assert candidate_response.status_code == 200, candidate_response.data
    item.refresh_from_db()
    assert item.attributes == before_candidate


@pytest.mark.django_db
def test_no_key_state_is_graceful_and_non_mutating(api_client, stamp_category):
    item = InventoryItem.objects.create(title="No key item", category=stamp_category)

    status_response = api_client.get("/api/ai/status/")
    assert status_response.status_code == 200
    assert status_response.data["configured"] is False
    assert status_response.data["enabled"] is False
    assert "Connect an AI provider" in status_response.data["disabled_reason"]

    identify_response = api_client.post(f"/api/items/{item.id}/ai/identify/")
    assert identify_response.status_code == 400
    assert "Connect an AI provider" in identify_response.data["detail"]
    assert FieldSuggestion.objects.filter(item=item).count() == 0


@pytest.mark.django_db
def test_ai_credential_is_encrypted_and_api_never_returns_key(api_client):
    response = api_client.post(
        "/api/ai/credential/",
        {
            "provider": AICredential.Provider.OPENAI,
            "model_id": "gpt-5.4-mini",
            "monthly_budget_cap_usd": "3.00",
            "api_key": "unit-test-key-material",
        },
        format="json",
    )

    assert response.status_code == 200, response.data
    assert "api_key" not in response.data
    assert response.data["configured"] is True
    credential = AICredential.objects.get()
    assert credential.api_key == "unit-test-key-material"
    with connection.cursor() as cursor:
        cursor.execute('select api_key from "intelligence_aicredential"')
        raw = cursor.fetchone()[0]
    assert raw != "unit-test-key-material"

    update_response = api_client.post(
        "/api/ai/credential/",
        {
            "provider": AICredential.Provider.OPENAI,
            "model_id": "gpt-5.5",
            "monthly_budget_cap_usd": "4.00",
            "api_key": "",
        },
        format="json",
    )

    assert update_response.status_code == 200, update_response.data
    assert "api_key" not in update_response.data
    credential.refresh_from_db()
    assert credential.api_key == "unit-test-key-material"
    assert credential.model_id == "gpt-5.5"
    assert str(credential.monthly_budget_cap_usd) == "4.00"
    assert "unit-test-key-material" not in str(AuditLog.objects.latest("created_at").payload)


@pytest.mark.django_db
def test_exif_stripping_is_asserted_before_send(stamp_category):
    item = InventoryItem.objects.create(title="Photo item", category=stamp_category)
    PhotoAsset.objects.create(
        item=item,
        original_path="originals/exif.jpg",
        processed_path="processed/exif.jpg",
    )
    original = image_bytes_with_exif()
    assert Image.open(BytesIO(original)).getexif()

    prepared = strip_exif_for_ai(original, photo_id="photo-1")
    assert prepared.exif_stripped is True
    assert not Image.open(BytesIO(prepared.data)).getexif()

    result = run_identify_for_item(
        item,
        adapter=FakeAiResearchAdapter(),
        storage=RecordingStorage({"processed/exif.jpg": original}),
    )
    assert result["call"].exif_stripped is True


@pytest.mark.django_db
def test_price_assist_surfaces_no_number_as_price(stamp_category):
    item = InventoryItem.objects.create(title="1932 bridge stamp", category=stamp_category)

    result = run_price_assist_for_item(item, adapter=PriceNoisyFakeAdapter())

    assert result["suggestions"] == []
    terms = list(AIResearchSearchTerm.objects.filter(item=item).values_list("phrase", flat=True))
    assert terms == ["1932 bridge stamp"]
    assert "$100 bridge stamp valuation" not in terms
    assert all("value" not in term.lower() for term in terms)
    assert result["call"].search_terms_created == 1


@pytest.mark.django_db
def test_price_assist_search_terms_feed_pricing_source_links(stamp_category):
    item = InventoryItem.objects.create(
        title="Australia bridge stamp",
        category=stamp_category,
        attributes={"country": "Australia", "year": 1932, "denomination": "2d"},
    )
    run_price_assist_for_item(item, adapter=FakeAiResearchAdapter())

    links = pricing_source_links(item)

    assert links
    assert {link.query for link in links} == {"Australia bridge stamp Australia 1932 2d exact variety"}
    assert links[0].url.startswith("https://www.ebay.com.au/sch/i.html?")


@pytest.mark.django_db
def test_reference_lookup_stores_view_only_links_not_images(stamp_category):
    item = InventoryItem.objects.create(title="Reference item", category=stamp_category)

    run_price_assist_for_item(item, adapter=FakeAiResearchAdapter())

    links = list(AIReferenceLink.objects.filter(item=item))
    assert links
    assert all(link.url.startswith("https://www.google.com/search") for link in links)
    assert PhotoAsset.objects.filter(item=item).count() == 0
    assert all("base64" not in link.url.lower() for link in links)


@pytest.mark.django_db
def test_audit_and_usage_records_are_secret_free(stamp_category):
    item = InventoryItem.objects.create(title="Audit item", category=stamp_category)

    result = run_identify_for_item(item, adapter=FakeAiResearchAdapter(), storage=RecordingStorage({}))

    call = result["call"]
    assert AIResearchCall.objects.get(id=call.id).estimated_cost_usd == Decimal("0.000100")
    audit = AuditLog.objects.filter(action="ai.research.identify.completed").latest("created_at")
    payload_text = str(audit.payload).lower()
    assert "provider" in audit.payload
    assert "key" not in payload_text
    assert "token" not in payload_text
    assert "secret" not in payload_text


@pytest.mark.django_db(transaction=True)
def test_backup_restore_includes_ai_tables(tmp_path, monkeypatch, stamp_category):
    if connection.vendor != "sqlite":
        pytest.skip("Sprint 8 backup command is SQLite-only.")
    item = InventoryItem.objects.create(title="Backup item", category=stamp_category)
    run_identify_for_item(item, adapter=FakeAiResearchAdapter(), storage=RecordingStorage({}))

    _, extract_dir = run_encrypted_backup(tmp_path, monkeypatch)
    manifest = load_backup_manifest(extract_dir)
    assert manifest["row_counts"]["intelligence.airesearchcall"] == 1
    assert manifest["row_counts"]["intelligence.airesearchsearchterm"] == 2
    assert manifest["row_counts"]["intelligence.aireferencelink"] == 2
    assert sqlite_count(extract_dir / DB_SNAPSHOT_NAME, "intelligence_airesearchcall") == 1
    assert sqlite_count(extract_dir / DB_SNAPSHOT_NAME, "intelligence_airesearchsearchterm") == 2
    assert sqlite_count(extract_dir / DB_SNAPSHOT_NAME, "intelligence_aireferencelink") == 2
