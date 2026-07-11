from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

import pytest
from django.conf import settings
from django.core.management import call_command
from django.urls import resolve
from django.utils import timezone
from rest_framework.test import APIClient

import integrations.ebay as ebay_integration
from apps.audit.models import AuditLog
from apps.core.backup_ops import DB_SNAPSHOT_NAME
from apps.core.tests.backup_helpers import (
    load_backup_manifest,
    run_encrypted_backup,
    sqlite_column_values,
    sqlite_count,
)
from apps.ebay.aspects import check_aspects, suggest_categories
from apps.ebay.constants import (
    AUDIT_INVENTORY_ITEM_UPSERTED,
    AUDIT_LOCATION_CREATED,
    AUDIT_MEDIA_UPLOADED,
    AUDIT_OFFER_CREATED,
    AUDIT_OFFER_UPDATED,
    AUDIT_OFFER_WITHDRAWN,
    AUDIT_PUBLISH_ATTEMPTED,
    AUDIT_PUBLISH_FAILED,
    AUDIT_PUBLISH_SUCCEEDED,
    AUDIT_TAXONOMY_ASPECTS_OVERRIDE,
    EBAY_SCOPES,
)
from apps.ebay.models import EbayAppToken, EbayCredential, MerchantLocation
from apps.ebay.publishing import publish_draft, staged_review
from apps.ebay.services import create_merchant_location, get_app_access_token
from apps.ebay.staging import _inventory_item_payload, stage_draft, withdraw_staged
from apps.inventory.models import InventoryItem
from apps.catalog.models import ProductCategory
from apps.listing.models import ChannelListing, ListingDraft
from apps.photos.models import PhotoAsset


TEST_FERNET_KEY = "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY="


@pytest.fixture(autouse=True)
def ebay_settings(settings, tmp_path):
    settings.EBAY_ENV = ""
    settings.EBAY_CLIENT_ID = ""
    settings.EBAY_CLIENT_SECRET = ""
    settings.EBAY_RU_NAME = ""
    settings.MAGPIE_TOKEN_ENCRYPTION_KEY = TEST_FERNET_KEY
    settings.MEDIA_ROOT = tmp_path / "media"
    ebay_integration.FakeEbayMediaAdapter.upload_count = 0
    ebay_integration.FakeEbayInventoryAdapter.offers = {}
    ebay_integration.FakeEbayInventoryAdapter.inventory_items = {}
    ebay_integration.FakeEbayInventoryAdapter.locations = {}
    ebay_integration.FakeEbayInventoryAdapter.offer_counter = 0
    ebay_integration.FakeEbayInventoryAdapter.create_count = 0
    ebay_integration.FakeEbayInventoryAdapter.update_count = 0
    ebay_integration.FakeEbayInventoryAdapter.withdraw_count = 0
    ebay_integration.FakeEbayInventoryAdapter.publish_count = 0
    ebay_integration.FakeEbayInventoryAdapter.publish_should_fail = False


@pytest.fixture
def user(django_user_model):
    return django_user_model.objects.create_user(username="sprint7", password="pass", is_staff=True)


@pytest.fixture
def api_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def category():
    return ProductCategory.objects.create(name="Stamps", slug="stamps", sku_prefix="STM", profile_key="stamps")


@pytest.fixture
def item(category):
    return InventoryItem.objects.create(
        title="First-flight postage stamp",
        category=category,
        status=InventoryItem.Status.READY_TO_LIST,
        condition=InventoryItem.Condition.GOOD,
        acquisition_cost="1.50",
        estimated_value="1.00",
    )


@pytest.fixture
def credential():
    return EbayCredential.objects.create(
        environment="sandbox",
        scopes=EBAY_SCOPES,
        refresh_token="refresh-token",
        access_token="access-token",
        access_token_expires_at=timezone.now() + timedelta(hours=1),
    )


@pytest.fixture
def merchant_location():
    return MerchantLocation.objects.create(
        environment="sandbox",
        merchant_location_key="first-flight-location",
        name="First Flight Location",
        country="AU",
        postal_code="2000",
        created_on_ebay=True,
        fetched_at=timezone.now(),
    )


def add_photo(item, path: str = "processed/photo.jpg"):
    full_path = Path(path)
    media_path = Path(settings.MEDIA_ROOT) / full_path
    media_path.parent.mkdir(parents=True, exist_ok=True)
    media_path.write_bytes(b"fake-jpeg")
    return PhotoAsset.objects.create(
        item=item,
        processed_path=str(full_path),
        original_path=str(full_path),
        order_index=item.photos.count(),
    )


def make_draft(item, *, specifics=None, channel_data=None, status=ListingDraft.Status.READY):
    return ListingDraft.objects.create(
        item=item,
        status=status,
        title="Postage stamp test listing",
        description_html="<p>Cheap postage stamp plumbing test.</p>",
        price="1.00",
        quantity=1,
        item_specifics=specifics
        if specifics is not None
        else [
            {"name": "Brand", "value": "Australia Post"},
            {"name": "Country/Region of Manufacture", "value": "Australia"},
        ],
        photo_ids=[str(photo.id) for photo in item.photos.order_by("order_index")]
        if item.photos.exists()
        else [],
        channel_data={
            "category_id": "105848",
            "category_tree_id": "15",
            "category_name": "Australian Stamps",
            "condition_id": "3000",
            "merchant_location_key": "first-flight-location",
            "payment_policy_id": "payment-1",
            "fulfillment_policy_id": "fulfillment-1",
            "return_policy_id": "return-1",
            **(channel_data or {}),
        },
    )


@pytest.mark.django_db
def test_stage_restage_and_withdraw_against_fakes(item, credential, merchant_location):
    add_photo(item)
    draft = make_draft(item)

    staged = stage_draft(draft)

    assert staged.status == ListingDraft.Status.STAGED
    assert staged.channel_data["offer_id"] == "fake-offer-1"
    assert staged.channel_data["inventory_item_sku"] == item.sku
    assert staged.channel_data["eps_image_urls"] == ["fake-eps://1.jpg"]
    assert staged.channel_data["last_payload_snapshot"]["offer"]["marketplaceId"] == "EBAY_AU"

    restaged = stage_draft(staged)
    assert restaged.channel_data["offer_id"] == "fake-offer-1"
    assert restaged.channel_data["eps_image_urls"] == ["fake-eps://2.jpg"]

    withdrawn = withdraw_staged(restaged)
    assert withdrawn.status == ListingDraft.Status.READY
    assert "offer_id" not in withdrawn.channel_data
    assert "staged_at" not in withdrawn.channel_data

    staged_after_withdraw = stage_draft(withdrawn)
    assert staged_after_withdraw.status == ListingDraft.Status.STAGED
    assert staged_after_withdraw.channel_data["offer_id"] == "fake-offer-1"
    assert staged_after_withdraw.channel_data["eps_image_urls"] == ["fake-eps://3.jpg"]

    actions = set(AuditLog.objects.values_list("action", flat=True))
    assert {
        AUDIT_MEDIA_UPLOADED,
        AUDIT_INVENTORY_ITEM_UPSERTED,
        AUDIT_OFFER_CREATED,
        AUDIT_OFFER_UPDATED,
        AUDIT_OFFER_WITHDRAWN,
    } <= actions


@pytest.mark.django_db
def test_withdraw_then_restage_recovers_existing_unpublished_offer_without_publish(
    item,
    credential,
    merchant_location,
):
    add_photo(item)
    draft = make_draft(item)

    staged = stage_draft(draft)
    original_offer_id = staged.channel_data["offer_id"]
    withdrawn = withdraw_staged(staged)
    assert "offer_id" not in withdrawn.channel_data
    assert ebay_integration.FakeEbayInventoryAdapter.offers[original_offer_id]["status"] == "UNPUBLISHED"

    restaged = stage_draft(withdrawn)

    assert restaged.status == ListingDraft.Status.STAGED
    assert restaged.item.status == InventoryItem.Status.READY_TO_LIST
    assert restaged.channel_data["offer_id"] == original_offer_id
    assert "listing_id" not in restaged.channel_data
    assert ebay_integration.FakeEbayInventoryAdapter.create_count == 1
    assert ebay_integration.FakeEbayInventoryAdapter.update_count == 1
    assert ebay_integration.FakeEbayInventoryAdapter.publish_count == 0
    assert AuditLog.objects.filter(action=AUDIT_OFFER_UPDATED).count() == 1
    assert not AuditLog.objects.filter(action=AUDIT_PUBLISH_ATTEMPTED).exists()


@pytest.mark.django_db
def test_stage_refuses_to_recover_published_offer(item, credential, merchant_location):
    add_photo(item)
    draft = make_draft(item)
    ebay_integration.FakeEbayInventoryAdapter.offers["fake-live-offer"] = {
        "offerId": "fake-live-offer",
        "sku": item.sku,
        "marketplaceId": "EBAY_AU",
        "format": "FIXED_PRICE",
        "status": "PUBLISHED",
        "listing": {"listingId": "fake-live-listing", "listingStatus": "ACTIVE"},
    }

    with pytest.raises(Exception, match="published"):
        stage_draft(draft)

    draft.refresh_from_db()
    assert draft.status == ListingDraft.Status.READY
    assert "offer_id" not in draft.channel_data
    assert "listing_id" not in draft.channel_data
    assert ebay_integration.FakeEbayInventoryAdapter.update_count == 0
    assert ebay_integration.FakeEbayInventoryAdapter.publish_count == 0
    assert not AuditLog.objects.filter(action=AUDIT_PUBLISH_ATTEMPTED).exists()


@pytest.mark.django_db
def test_inventory_payload_serializes_condition_enum_from_condition_id(item):
    add_photo(item)
    item.condition = InventoryItem.Condition.UNGRADED
    item.save(update_fields=["condition", "updated_at"])
    draft = make_draft(item, channel_data={"condition_id": "3000"})

    payload = _inventory_item_payload(draft, ["fake-eps://1.jpg"])

    assert payload["condition"] == "USED_EXCELLENT"
    assert isinstance(payload["condition"], str)
    assert payload["condition"] != "USED"
    assert "condition_id" not in payload


@pytest.mark.django_db
def test_stage_guards_zero_photo_many_photos_missing_fields_and_conflict(item, credential, merchant_location):
    no_photo = make_draft(item)
    with pytest.raises(Exception, match="At least one photo"):
        stage_draft(no_photo)

    no_photo.delete()
    for index in range(25):
        add_photo(item, f"processed/photo-{index}.jpg")
    too_many = make_draft(item)
    with pytest.raises(Exception, match="24 photos"):
        stage_draft(too_many)

    item.photos.all().delete()
    add_photo(item)
    too_many.delete()
    missing = make_draft(item, channel_data={"category_id": ""})
    with pytest.raises(Exception, match="category_id"):
        stage_draft(missing)

    missing.delete()
    staged = make_draft(item, status=ListingDraft.Status.STAGED, channel_data={"offer_id": "existing"})
    conflict = make_draft(item)
    with pytest.raises(Exception, match="unresolved eBay state"):
        stage_draft(conflict)
    staged.delete()


@pytest.mark.django_db
def test_aspects_block_and_override_path(item, credential, merchant_location):
    add_photo(item)
    draft = make_draft(item, specifics=[{"name": "Brand", "value": "Australia Post"}])

    aspect_result = check_aspects(draft)
    assert aspect_result["missing_required"] == ["Country/Region of Manufacture"]
    with pytest.raises(Exception, match="Missing required eBay aspects"):
        stage_draft(draft)

    staged = stage_draft(draft, override_missing_aspects=True, override_reason="first-flight check")
    assert staged.status == ListingDraft.Status.STAGED
    override = AuditLog.objects.filter(action=AUDIT_TAXONOMY_ASPECTS_OVERRIDE).latest("created_at")
    assert override.payload["missing_required"] == ["Country/Region of Manufacture"]
    assert override.payload["reason"] == "first-flight check"


@pytest.mark.django_db
def test_stage_blocks_non_leaf_category(item, credential, merchant_location):
    add_photo(item)
    draft = make_draft(
        item,
        channel_data={
            "category_id": "260",
            "category_tree_id": "15",
            "category_name": "Stamps",
        },
    )

    with pytest.raises(ebay_integration.EbayUnavailable, match="leaf category"):
        stage_draft(draft)

    draft.refresh_from_db()
    assert draft.status == ListingDraft.Status.READY
    assert "offer_id" not in draft.channel_data
    assert "listing_id" not in draft.channel_data


@pytest.mark.django_db
def test_publish_gate_success_failure_and_restage(item, credential, merchant_location):
    add_photo(item)
    draft = stage_draft(make_draft(item))

    with pytest.raises(Exception, match="exact SKU"):
        publish_draft(draft, confirm_sku="wrong")

    review = staged_review(draft)
    assert review["offer_id"] == draft.channel_data["offer_id"]
    assert review["photo_count"] == 1

    ebay_integration.FakeEbayInventoryAdapter.publish_should_fail = True
    with pytest.raises(ebay_integration.EbayUnavailable):
        publish_draft(draft, confirm_sku=item.sku)
    draft.refresh_from_db()
    assert draft.status == ListingDraft.Status.PUBLISH_FAILED
    assert draft.channel_data["last_ebay_error"]
    assert ChannelListing.objects.count() == 0
    assert AuditLog.objects.filter(action=AUDIT_PUBLISH_FAILED).exists()

    ebay_integration.FakeEbayInventoryAdapter.publish_should_fail = False
    restaged = stage_draft(draft)
    published = publish_draft(restaged, confirm_sku=item.sku)
    published.item.refresh_from_db()
    assert published.status == ListingDraft.Status.PUBLISHED
    assert published.channel_data["listing_id"].startswith("fake-listing-")
    assert published.item.status == InventoryItem.Status.LISTED
    channel_listing = ChannelListing.objects.get(source_listing_draft=published)
    assert channel_listing.channel == ChannelListing.Channel.EBAY
    assert channel_listing.item == published.item
    assert channel_listing.url == f"https://www.ebay.com.au/itm/{published.channel_data['listing_id']}"
    assert channel_listing.ended_at is None
    assert AuditLog.objects.filter(action=AUDIT_PUBLISH_ATTEMPTED).count() == 2
    assert AuditLog.objects.filter(action=AUDIT_PUBLISH_SUCCEEDED).count() == 1


@pytest.mark.django_db
def test_publish_refuses_second_publish_without_calling_ebay(item, credential, merchant_location):
    add_photo(item)
    draft = stage_draft(make_draft(item))
    published = publish_draft(draft, confirm_sku=item.sku)
    assert published.status == ListingDraft.Status.PUBLISHED
    assert published.channel_data["listing_id"]
    assert ebay_integration.FakeEbayInventoryAdapter.publish_count == 1
    assert ChannelListing.objects.filter(source_listing_draft=published).count() == 1

    with pytest.raises(Exception, match="published eBay listing"):
        publish_draft(published, confirm_sku=item.sku)

    published.refresh_from_db()
    published.item.refresh_from_db()
    assert published.status == ListingDraft.Status.PUBLISHED
    assert published.item.status == InventoryItem.Status.LISTED
    assert ChannelListing.objects.filter(source_listing_draft=published).count() == 1
    assert ebay_integration.FakeEbayInventoryAdapter.publish_count == 1
    assert AuditLog.objects.filter(action=AUDIT_PUBLISH_ATTEMPTED).count() == 1
    assert AuditLog.objects.filter(action=AUDIT_PUBLISH_SUCCEEDED).count() == 1


@pytest.mark.django_db
def test_publish_refuses_stale_staged_draft_with_listing_id(item, credential, merchant_location):
    add_photo(item)
    draft = stage_draft(make_draft(item))
    channel_data = dict(draft.channel_data)
    channel_data["listing_id"] = "already-live"
    draft.channel_data = channel_data
    draft.save(update_fields=["channel_data", "updated_at"])

    with pytest.raises(Exception, match="published eBay listing"):
        publish_draft(draft, confirm_sku=item.sku)

    draft.refresh_from_db()
    assert draft.status == ListingDraft.Status.STAGED
    assert draft.channel_data["listing_id"] == "already-live"
    assert ebay_integration.FakeEbayInventoryAdapter.publish_count == 0
    assert not AuditLog.objects.filter(action=AUDIT_PUBLISH_ATTEMPTED).exists()


@pytest.mark.django_db
def test_app_token_independent_from_seller_credential(credential):
    access_token = get_app_access_token()
    assert access_token.startswith("fake-app-token")
    assert EbayAppToken.objects.count() == 1

    EbayCredential.objects.all().delete()
    assert EbayAppToken.objects.count() == 1

    EbayCredential.objects.create(
        environment="sandbox",
        scopes=EBAY_SCOPES,
        refresh_token="refresh-token-2",
        access_token="access-token-2",
        access_token_expires_at=timezone.now() + timedelta(hours=1),
    )
    EbayAppToken.objects.all().delete()
    assert EbayCredential.objects.count() == 1


@pytest.mark.django_db
def test_merchant_location_command_and_service_create_once(credential):
    call_command(
        "create_merchant_location",
        "--key",
        "loc-1",
        "--name",
        "Test Location",
        "--country",
        "AU",
        "--postal-code",
        "2000",
    )
    location = MerchantLocation.objects.get()
    assert location.created_on_ebay is True
    assert location.merchant_location_key == "loc-1"
    assert AuditLog.objects.filter(action=AUDIT_LOCATION_CREATED).count() == 1

    same = create_merchant_location(
        merchant_location_key="loc-1",
        name="Test Location",
        country="AU",
        postal_code="2000",
    )
    assert same.pk == location.pk
    assert AuditLog.objects.filter(action=AUDIT_LOCATION_CREATED).count() == 1


@pytest.mark.django_db
def test_taxonomy_suggestions_unsupported_in_sandbox_and_available_in_production(monkeypatch):
    sandbox = suggest_categories(q="stamp")
    assert sandbox == {
        "supported": False,
        "suggestions": [],
        "detail": "Category suggestions are unavailable outside production.",
    }

    monkeypatch.setattr(ebay_integration, "effective_environment", lambda: "production")
    monkeypatch.setattr(
        ebay_integration,
        "get_ebay_taxonomy_adapter",
        lambda access_token=None: ebay_integration.FakeEbayTaxonomyAdapter(
            environment="production",
            access_token=access_token,
        ),
    )
    result = suggest_categories(q="stamp")
    assert result["supported"] is True
    non_leaf, leaf = result["suggestions"]
    assert non_leaf["category_id"] == "260"
    assert non_leaf["category_name"] == "Stamps"
    assert non_leaf["category_path"] == ["Stamps"]
    assert non_leaf["is_leaf"] is False
    assert leaf["category_id"] == "105848"
    assert leaf["category_name"] == "Australian Stamps"
    assert leaf["category_path"] == ["Stamps", "Australia", "Australian Stamps"]
    assert leaf["is_leaf"] is True


@pytest.mark.django_db(transaction=True)
def test_backup_includes_sprint7_ebay_tables(tmp_path, monkeypatch, credential):
    EbayAppToken.objects.create(
        environment="sandbox",
        access_token="app-token",
        expires_at=timezone.now() + timedelta(hours=1),
    )
    MerchantLocation.objects.create(
        environment="sandbox",
        merchant_location_key="loc-1",
        name="Location",
        country="AU",
        postal_code="2000",
    )
    _, extract_dir = run_encrypted_backup(tmp_path, monkeypatch)
    manifest = load_backup_manifest(extract_dir)

    assert manifest["row_counts"]["ebay.ebayapptoken"] == 1
    assert manifest["row_counts"]["ebay.merchantlocation"] == 1
    restored_db = extract_dir / DB_SNAPSHOT_NAME
    [(snapshot_app_token,)] = sqlite_column_values(
        restored_db,
        "ebay_ebayapptoken",
        "access_token",
    )
    assert snapshot_app_token != "app-token"
    assert sqlite_count(restored_db, "ebay_merchantlocation") == 1


@pytest.mark.django_db
def test_listing_draft_sprint7_api_paths(api_client, item, credential, merchant_location):
    add_photo(item)
    draft = make_draft(item)

    aspects = api_client.get(f"/api/listing-drafts/{draft.id}/aspects-check/")
    assert aspects.status_code == 200
    assert aspects.data["missing_required"] == []

    stage = api_client.post(f"/api/listing-drafts/{draft.id}/stage/", {}, format="json")
    assert stage.status_code == 200, stage.data
    review = api_client.get(f"/api/listing-drafts/{draft.id}/staged-review/")
    assert review.status_code == 200, review.data
    publish = api_client.post(
        f"/api/listing-drafts/{draft.id}/publish/",
        {"confirm_sku": "wrong"},
        format="json",
    )
    assert publish.status_code == 400

    MerchantLocation.objects.all().delete()
    location = api_client.post(
        "/api/ebay/merchant-location/",
        {
            "merchant_location_key": "api-loc-1",
            "name": "API Location",
            "country": "AU",
            "postal_code": "2000",
        },
        format="json",
    )
    assert location.status_code == 201, location.data
    assert location.data["configured"] is True
    assert location.data["location"]["merchant_location_key"] == "api-loc-1"


def test_sprint7_url_wiring():
    draft_id = "54220841-1842-4dc4-b1a0-aa4dc8f521ce"

    assert resolve("/api/ebay/category-suggestions/").url_name == "ebay-category-suggestions"
    assert (
        resolve(f"/api/listing-drafts/{draft_id}/aspects-check/").url_name
        == "listing-draft-aspects-check"
    )
