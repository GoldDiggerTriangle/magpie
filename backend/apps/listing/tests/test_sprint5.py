from decimal import Decimal
from html.parser import HTMLParser
import inspect
import json
import uuid
import zipfile

import pytest
from django.core.management import call_command
from rest_framework.test import APIClient

from apps.catalog.models import ProductCategory
from apps.core.backup_ops import DB_SNAPSHOT_NAME
from apps.core.tests.backup_helpers import (
    load_backup_manifest,
    run_encrypted_backup,
    sqlite_count,
)
from apps.inventory.models import InventoryItem
from apps.listing.constants import ALLOWED_HTML_TAGS, BLOCKED_FIELDS, EBAY_TITLE_MAX
from apps.listing.context import safe_context
from apps.listing.generators import generator_for
from apps.listing.models import ListingBoilerplate, ListingDraft
from apps.listing.readiness import check_readiness
from apps.listing.specifics import build_specifics
from apps.photos.models import PhotoAsset
from apps.valuation.models import ValuationReport
from apps.valuation.services import set_current


@pytest.fixture
def user(django_user_model):
    return django_user_model.objects.create_user(username="listing", password="pass")


@pytest.fixture
def api_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def categories():
    return {
        "phones": ProductCategory.objects.create(
            name="Phones & Electronics",
            slug="phones-sprint5",
            sku_prefix="PH",
            profile_key="phones",
        ),
        "stamps": ProductCategory.objects.create(
            name="Stamps",
            slug="stamps-sprint5",
            sku_prefix="STM",
            profile_key="stamps",
        ),
        "coins": ProductCategory.objects.create(
            name="Coins",
            slug="coins-sprint5",
            sku_prefix="COIN",
            profile_key="coins",
        ),
        "gold": ProductCategory.objects.create(
            name="Gold",
            slug="gold-sprint5",
            sku_prefix="GOLD",
            profile_key="gold",
        ),
        "tools": ProductCategory.objects.create(
            name="Tools",
            slug="tools-sprint5",
            sku_prefix="TOOL",
            profile_key="",
        ),
    }


@pytest.fixture
def boilerplate():
    return ListingBoilerplate.objects.create(
        channel="ebay_au",
        name="Test boilerplate",
        body_html="<h2>Postage</h2><p>Tracked postage and standard payment terms.</p>",
    )


def create_phone(categories, **overrides):
    data = {
        "title": "Samsung Galaxy S21 test handset",
        "category": categories["phones"],
        "status": InventoryItem.Status.READY_TO_LIST,
        "condition": InventoryItem.Condition.GOOD,
        "acquisition_cost": Decimal("30.00"),
        "refurb_cost": Decimal("10.00"),
        "inbound_shipping_cost": Decimal("5.00"),
        "est_outbound_shipping": Decimal("12.00"),
        "est_packaging_cost": Decimal("2.00"),
        "estimated_value": Decimal("180.00"),
        "min_price": Decimal("100.00"),
        "target_price": Decimal("190.00"),
        "notes": "Internal note must not leak.",
        "attributes": {
            "brand": "Samsung",
            "model": "Galaxy S21",
            "storage_gb": 128,
            "ram_gb": 8,
            "colour": "Black",
            "network_status": "unlocked",
            "battery_health_pct": 88,
            "faults": "light rear scratch",
            "accessories": "USB cable",
            "imei": "359999999999999",
            "serial_no": "SNPRIVATE123",
            "notes": "Private phone note",
            "purchase_price": "20.00",
            "true_cost": "45.00",
            "supplier": "Secret supplier",
        },
    }
    data.update(overrides)
    return InventoryItem.objects.create(**data)


def create_photo(item, processed_path="processed/test.jpg", order_index=0):
    return PhotoAsset.objects.create(
        item=item,
        order_index=order_index,
        original_path=f"originals/{uuid.uuid4().hex}.jpg",
        processed_path=processed_path,
        thumb_path=f"thumbs/{uuid.uuid4().hex}.jpg",
    )


class TagCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = set()

    def handle_starttag(self, tag, attrs):
        self.tags.add(tag)

    def handle_startendtag(self, tag, attrs):
        self.tags.add(tag)


def generated_description(item, boilerplate_html=""):
    specifics = build_specifics(item)
    ctx = safe_context(item)
    return generator_for(item).description_html(
        ctx,
        specifics=specifics,
        boilerplate_html=boilerplate_html,
        sku_footer="",
    )


@pytest.mark.django_db
def test_listing_models_defaults_and_choices(categories):
    item = create_phone(categories)
    draft = ListingDraft.objects.create(item=item)

    assert draft.status == ListingDraft.Status.DRAFT
    assert draft.channel == "ebay_au"
    assert draft.listing_format == ListingDraft.Format.FIXED
    assert draft.quantity == 1


@pytest.mark.django_db
def test_safe_context_blocks_private_fields_and_generated_text(categories, boilerplate):
    item = create_phone(categories)
    ctx = safe_context(item)

    flattened = json.dumps(ctx).lower()
    for field in BLOCKED_FIELDS:
        assert field not in ctx
    for leaked_value in [
        "359999999999999",
        "SNPRIVATE123",
        "30.00",
        "Secret supplier",
        "Internal note",
    ]:
        assert leaked_value.lower() not in flattened

    generator = generator_for(item)
    specifics = build_specifics(item)
    title = generator.title(ctx)
    description = generator.description_html(
        ctx,
        specifics=specifics,
        boilerplate_html=boilerplate.body_html,
        sku_footer="",
    )
    generated = json.dumps(
        {"title": title, "description": description, "specifics": specifics}
    ).lower()
    assert item.sku.lower() not in generated
    for leaked_value in ["359999999999999", "snprivate123", "30.00", "secret supplier"]:
        assert leaked_value not in generated

    with_sku = generator.description_html(
        ctx,
        specifics=specifics,
        boilerplate_html="",
        sku_footer=item.sku,
    )
    assert item.sku in with_sku


@pytest.mark.django_db
def test_cert_number_allowed_for_coin_specifics_and_title(categories):
    coin = InventoryItem.objects.create(
        title="Certified coin",
        category=categories["coins"],
        condition=InventoryItem.Condition.GOOD,
        attributes={
            "country": "Australia",
            "year": 1937,
            "denomination": "Crown",
            "ruler_or_reign": "George VI",
            "grade": "VF",
            "cert": {"grader": "PCGS", "cert_no": "12345678"},
        },
    )

    ctx = safe_context(coin)
    assert ctx["cert_no"] == "12345678"
    assert "12345678" in generator_for(coin).title(ctx)
    assert {"name": "Certification Number", "value": "12345678"} in build_specifics(coin)


@pytest.mark.django_db
def test_generated_descriptions_use_safe_html_tags_for_all_profiles(categories):
    items = [
        create_phone(categories),
        InventoryItem.objects.create(
            title="Stamp",
            category=categories["stamps"],
            condition=InventoryItem.Condition.GOOD,
            attributes={
                "country": "Australia",
                "year": 1932,
                "denomination": "2d",
                "topic_theme": "Bridge",
                "catalogue_refs": [{"system": "SG", "number": "144"}],
            },
        ),
        InventoryItem.objects.create(
            title="Coin",
            category=categories["coins"],
            condition=InventoryItem.Condition.GOOD,
            attributes={"country": "Australia", "year": 1937, "denomination": "Crown"},
        ),
        InventoryItem.objects.create(
            title="Gold",
            category=categories["gold"],
            condition=InventoryItem.Condition.GOOD,
            attributes={"metal": "gold", "weight_g": "8.5", "fineness": "0.375", "form": "jewellery"},
        ),
        InventoryItem.objects.create(
            title="Generic tool",
            category=categories["tools"],
            condition=InventoryItem.Condition.GOOD,
            attributes={"internal": "ignored"},
        ),
    ]

    for item in items:
        description = generated_description(item)
        parser = TagCollector()
        parser.feed(description)
        assert parser.tags <= ALLOWED_HTML_TAGS
        assert "href=" not in description.lower()
        assert "<a" not in description.lower()
        assert len(generator_for(item).title(safe_context(item))) <= EBAY_TITLE_MAX


@pytest.mark.django_db
def test_readiness_failures_warnings_and_ready_gate(api_client, categories, boilerplate):
    item = create_phone(
        categories,
        condition=InventoryItem.Condition.UNGRADED,
        attributes={
            "brand": "Samsung",
            "model": "Galaxy S21",
            "storage_gb": 128,
            "network_status": "unlocked",
            "imei": "359999999999999",
            "serial_no": "SNPRIVATE123",
        },
    )
    ValuationReport.objects.create(
        item=item,
        suggested_price=Decimal("80.00"),
        min_acceptable_price=Decimal("100.00"),
        is_current=True,
    )
    draft = ListingDraft.objects.create(
        item=item,
        title="x" * 81,
        description_html="IMEI 359999999999999 serial SNPRIVATE123",
        price=Decimal("0.00"),
        quantity=0,
        item_specifics=[],
        photo_ids=[str(uuid.uuid4())],
    )

    by_key = {check.key: check.level for check in check_readiness(draft)}
    for key in {
        "title_too_long",
        "price_invalid",
        "quantity_invalid",
        "leak_imei",
        "leak_serial",
        "photos_unresolvable",
    }:
        assert by_key[key] == "fail"
    for key in {
        "fewer_than_3_photos",
        "condition_missing",
        "item_specifics_empty",
        "no_price_source",
        "price_below_min_acceptable",
        "price_below_true_cost",
        "no_boilerplate",
        "phones_faults_absent",
        "missing_whats_included",
    }:
        assert by_key[key] == "warn"

    sold_item = create_phone(
        categories,
        title="Sold phone",
        status=InventoryItem.Status.SOLD,
        attributes={"brand": "Samsung", "model": "Sold"},
    )
    sold_draft = ListingDraft.objects.create(
        item=sold_item,
        title="",
        description_html="",
        price=None,
        quantity=1,
        photo_ids=[],
    )
    sold_by_key = {check.key: check.level for check in check_readiness(sold_draft)}
    for key in {"no_photos", "title_missing", "description_missing", "price_invalid", "item_unavailable"}:
        assert sold_by_key[key] == "fail"

    uncategorised = InventoryItem.objects.create(
        title="No category",
        category=None,
        condition=InventoryItem.Condition.GOOD,
    )
    no_category_draft = ListingDraft.objects.create(
        item=uncategorised,
        title="No category title",
        description_html="<h2>What's included</h2><p>Item pictured only.</p>",
        price=Decimal("10.00"),
        quantity=1,
        photo_ids=[str(create_photo(uncategorised).id)],
    )
    no_category_by_key = {
        check.key: check.level for check in check_readiness(no_category_draft)
    }
    assert no_category_by_key["category_missing"] == "warn"

    blocked = api_client.patch(
        f"/api/listing-drafts/{sold_draft.id}/",
        {"status": "ready"},
        format="json",
    )
    assert blocked.status_code == 400
    assert "readiness" in blocked.data

    photo = create_photo(item, processed_path="processed/valid.jpg")
    ready = ListingDraft.objects.create(
        item=item,
        title="Ready title",
        description_html="<h2>What's included</h2><p>$45 postage is fine.</p>",
        price=Decimal("120.00"),
        quantity=1,
        item_specifics=[{"name": "Brand", "value": "Samsung"}],
        photo_ids=[str(photo.id)],
        boilerplate=boilerplate,
        generated_meta={"price_source": {"value": "120.00"}},
    )
    response = api_client.patch(
        f"/api/listing-drafts/{ready.id}/",
        {"status": "ready"},
        format="json",
    )
    assert response.status_code == 200, response.data
    assert response.data["status"] == "ready"
    assert {check.key: check.level for check in check_readiness(ready)}["leak_imei"] == "pass"


@pytest.mark.django_db
def test_item_create_api_defaults_price_source_and_regenerate_semantics(api_client, categories, boilerplate):
    item = create_phone(categories)
    report = ValuationReport.objects.create(
        item=item,
        estimate_median=Decimal("180.00"),
        suggested_price=Decimal("199.00"),
        min_acceptable_price=Decimal("120.00"),
        currency="AUD",
    )
    set_current(report)
    create_photo(item)

    create = api_client.post(f"/api/items/{item.id}/listing-drafts/", {}, format="json")
    assert create.status_code == 201, create.data
    draft_id = create.data["id"]
    assert Decimal(create.data["price"]) == Decimal("199.00")
    assert create.data["generated_meta"]["price_source"]["valuation_report_id"] == str(report.id)
    assert create.data["title"]
    assert create.data["item_specifics"]
    assert create.data["photo_ids"]
    assert "<h2>Postage</h2>" in create.data["description_html"]

    patch = api_client.patch(
        f"/api/listing-drafts/{draft_id}/",
        {"title": "Human edited title"},
        format="json",
    )
    assert patch.status_code == 200
    assert patch.data["title_edited"] is True

    rejected = api_client.post(
        f"/api/listing-drafts/{draft_id}/generate/",
        {"fields": ["title"], "confirm_overwrite": False},
        format="json",
    )
    assert rejected.status_code == 400
    assert rejected.data["protected_fields"] == ["title"]

    accepted = api_client.post(
        f"/api/listing-drafts/{draft_id}/generate/",
        {"fields": ["title", "description", "specifics", "price"], "confirm_overwrite": True},
        format="json",
    )
    assert accepted.status_code == 200, accepted.data
    assert accepted.data["title_edited"] is False
    assert accepted.data["description_edited"] is False
    assert Decimal(accepted.data["price"]) == Decimal("199.00")


@pytest.mark.django_db
def test_export_zip_structure_skips_missing_photos_and_sets_exported(api_client, settings, tmp_path, categories, boilerplate):
    settings.MEDIA_ROOT = tmp_path
    item = create_phone(categories)
    existing = create_photo(item, processed_path="processed/export.jpg")
    (tmp_path / "processed").mkdir()
    (tmp_path / "processed" / "export.jpg").write_bytes(b"jpeg-bytes")
    missing_id = uuid.uuid4()
    draft = ListingDraft.objects.create(
        item=item,
        title="Export title",
        subtitle="Subtitle",
        description_html="<h2>What's included</h2><p>USB cable.</p>",
        price=Decimal("99.00"),
        item_specifics=[{"name": "Brand", "value": "Samsung"}],
        photo_ids=[str(existing.id), str(missing_id)],
        boilerplate=boilerplate,
    )

    response = api_client.get(f"/api/listing-drafts/{draft.id}/export/")

    assert response.status_code == 200
    assert response["content-type"] == "application/zip"
    draft.refresh_from_db()
    assert draft.status == ListingDraft.Status.EXPORTED
    assert draft.exported_at is not None

    archive_path = tmp_path / "listing.zip"
    archive_path.write_bytes(response.content)
    with zipfile.ZipFile(archive_path) as archive:
        names = set(archive.namelist())
        assert names == {
            "title.txt",
            "subtitle.txt",
            "description.html",
            "specifics.csv",
            "readiness.json",
            "listing-summary.json",
            f"photos/01_{item.sku}.jpg",
        }
        assert archive.read("title.txt").decode() == "Export title"
        assert archive.read(f"photos/01_{item.sku}.jpg") == b"jpeg-bytes"
        readiness = json.loads(archive.read("readiness.json"))
        summary = json.loads(archive.read("listing-summary.json"))

    assert str(missing_id) in readiness["skipped_photo_ids"]
    assert summary["status"] == "exported"
    assert summary["item_sku"] == item.sku


@pytest.mark.django_db
def test_boilerplate_api_read_only_crud_and_unauthenticated(api_client, categories, boilerplate):
    item = create_phone(categories)
    draft = ListingDraft.objects.create(item=item, title="CRUD", price=Decimal("10.00"))

    list_response = api_client.get("/api/listing-boilerplates/")
    assert list_response.status_code == 200
    assert list_response.data["count"] == 1
    create = api_client.post(
        "/api/listing-boilerplates/",
        {"name": "Nope", "channel": "ebay_au"},
        format="json",
    )
    assert create.status_code == 405

    detail = api_client.get(f"/api/listing-drafts/{draft.id}/")
    assert detail.status_code == 200
    patch = api_client.patch(
        f"/api/listing-drafts/{draft.id}/",
        {"subtitle": "patched"},
        format="json",
    )
    assert patch.status_code == 200
    delete = api_client.delete(f"/api/listing-drafts/{draft.id}/")
    assert delete.status_code == 204

    anon = APIClient()
    unauth = anon.get(f"/api/items/{item.id}/listing-drafts/")
    assert unauth.status_code in {401, 403}


@pytest.mark.django_db(transaction=True)
def test_backup_json_restore_includes_listing_tables(tmp_path, monkeypatch, categories, boilerplate):
    item = create_phone(categories)
    ListingDraft.objects.create(
        item=item,
        title="Backup draft",
        description_html="<h2>What's included</h2><p>USB cable.</p>",
        price=Decimal("50.00"),
        boilerplate=boilerplate,
    )

    _, extract_dir = run_encrypted_backup(tmp_path, monkeypatch)
    manifest = load_backup_manifest(extract_dir)

    assert manifest["row_counts"]["listing.listingboilerplate"] == 1
    assert manifest["row_counts"]["listing.listingdraft"] == 1
    restored_db = extract_dir / DB_SNAPSHOT_NAME
    assert sqlite_count(restored_db, "listing_listingboilerplate") == 1
    assert sqlite_count(restored_db, "listing_listingdraft") == 1


def test_listing_app_has_no_network_client_imports():
    import apps.listing.context as context_module
    import apps.listing.export as export_module
    import apps.listing.generators as generators_module
    import apps.listing.readiness as readiness_module
    import apps.listing.specifics as specifics_module
    import apps.listing.views as views_module

    source = "\n".join(
        inspect.getsource(module)
        for module in [
            context_module,
            export_module,
            generators_module,
            readiness_module,
            specifics_module,
            views_module,
        ]
    )
    for token in ["requests", "httpx", "aiohttp", "urllib", "urlopen", "openai"]:
        assert token not in source.lower()
