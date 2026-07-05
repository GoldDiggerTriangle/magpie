from __future__ import annotations

import inspect
import zipfile
from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.catalog.models import ProductCategory
from apps.inventory.models import InventoryItem
from apps.listing import channel_listings, copy_packs
from apps.listing.models import ChannelListing, ListingDraft
from apps.photos.models import PhotoAsset, PhotoDerivative
from apps.profit.models import ProfitSetting
from apps.sales.models import SaleRecord


pytestmark = pytest.mark.django_db


@pytest.fixture
def user(django_user_model):
    return django_user_model.objects.create_user(username="sprint22", password="pass")


@pytest.fixture
def api_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def category():
    return ProductCategory.objects.create(
        name="Sprint 22 Stamps",
        slug="sprint-22-stamps",
        sku_prefix="S22",
        profile_key="stamps",
    )


@pytest.fixture
def setting():
    return ProfitSetting.objects.create(seller_mode=ProfitSetting.SellerMode.FREE_SELLING)


def make_item(category=None, **overrides):
    data = {
        "title": "Kangaroo 2d red stamp",
        "category": category,
        "condition": InventoryItem.Condition.GOOD,
        "target_price": Decimal("95.00"),
        "acquisition_cost": Decimal("20.00"),
        "attributes": {"country": "Australia", "denomination": "2d"},
    }
    data.update(overrides)
    return InventoryItem.objects.create(**data)


def test_copy_pack_templates_are_data_and_render_golden_channels(category):
    item = make_item(category)

    registry = copy_packs.load_template_registry()
    assert set(registry) == {"ebay", "facebook_marketplace", "gumtree", "generic"}
    assert copy_packs.TEMPLATE_PATH.name == "copy_pack_templates.json"

    golden = {
        "ebay": "Price: A$95.00",
        "facebook_marketplace": "Price: A$95.00",
        "gumtree": "Asking price: A$95.00",
        "generic": "Price: A$95.00",
    }
    for channel, expected_price_line in golden.items():
        pack = copy_packs.render_copy_pack(item, channel=channel)
        assert pack["sections"]["title"] == "Kangaroo 2d red stamp"
        assert pack["sections"]["price_line"] == expected_price_line
        assert pack["channel"] == channel


def test_copy_pack_missing_fields_visible_and_price_never_generated(category):
    item = make_item(
        None,
        title="",
        target_price=None,
        estimated_value=Decimal("500.00"),
        min_price=Decimal("100.00"),
        attributes={},
    )
    pack = copy_packs.render_copy_pack(item, channel="ebay")

    assert "[title not set]" in pack["sections"]["title"]
    assert "[category not set]" in pack["sections"]["description"]
    assert "[details not set]" in pack["sections"]["description"]
    assert "[price not set" in pack["sections"]["price_line"]
    assert pack["price_source"]["basis"] == "missing"
    assert "500.00" not in pack["whole_ad"]
    for forbidden in ["mint", "rare", "perfect", "tested"]:
        assert forbidden not in pack["whole_ad"].lower()

    evidence = copy_packs.render_copy_pack(
        item,
        channel="generic",
        evidence_price="123.45",
        evidence_label="approved comp #1",
    )
    assert evidence["sections"]["price_line"] == "Price: A$123.45"
    assert evidence["price_source"]["basis"] == "human_picked_evidence"
    assert evidence["price_source"]["label"] == "approved comp #1"


def test_photo_zip_exports_approved_derivative_first_then_original(api_client, settings, tmp_path, category):
    settings.MEDIA_ROOT = tmp_path
    item = make_item(category)
    (tmp_path / "originals").mkdir()
    (tmp_path / "fixed").mkdir()
    (tmp_path / "originals" / "one.jpg").write_bytes(b"original-one")
    (tmp_path / "fixed" / "one.jpg").write_bytes(b"fixed-one")
    (tmp_path / "originals" / "two.jpg").write_bytes(b"original-two")
    photo_one = PhotoAsset.objects.create(
        item=item,
        role=PhotoAsset.Role.MAIN,
        order_index=0,
        original_path="originals/one.jpg",
    )
    derivative = PhotoDerivative.objects.create(
        photo=photo_one,
        status=PhotoDerivative.Status.APPROVED,
        fixed_path="fixed/one.jpg",
        source_path="originals/one.jpg",
    )
    photo_one.active_derivative = derivative
    photo_one.save(update_fields=["active_derivative"])
    PhotoAsset.objects.create(
        item=item,
        role=PhotoAsset.Role.DETAIL,
        order_index=1,
        original_path="originals/two.jpg",
    )

    response = api_client.get(f"/api/items/{item.id}/photos/export.zip/")

    assert response.status_code == 200
    archive_path = tmp_path / "photos.zip"
    archive_path.write_bytes(response.content)
    with zipfile.ZipFile(archive_path) as archive:
        names = set(archive.namelist())
        assert f"photos/01_{item.sku}_fixed.jpg" in names
        assert f"photos/02_{item.sku}_original.jpg" in names
        assert archive.read(f"photos/01_{item.sku}_fixed.jpg") == b"fixed-one"
        assert archive.read(f"photos/02_{item.sku}_original.jpg") == b"original-two"


def test_ebay_seed_uses_local_records_only_skips_ambiguous_and_is_idempotent(category):
    clear_item = make_item(category, title="Clear eBay seed")
    ambiguous_item = make_item(category, title="Ambiguous eBay seed")
    draft = ListingDraft.objects.create(
        item=clear_item,
        status=ListingDraft.Status.PUBLISHED,
        channel_data={"listing_id": "EBAY-1", "published_at": "2026-06-10T10:00:00+10:00"},
    )
    ListingDraft.objects.create(
        item=ambiguous_item,
        status=ListingDraft.Status.PUBLISHED,
        channel_data={"listing_id": "EBAY-2", "published_at": "2026-06-10"},
    )
    ListingDraft.objects.create(
        item=ambiguous_item,
        status=ListingDraft.Status.PUBLISHED,
        channel_data={"listing_id": "EBAY-3", "published_at": "2026-06-11"},
    )

    first = channel_listings.seed_ebay_channel_listings()
    second = channel_listings.seed_ebay_channel_listings()

    assert first.seeded == 1
    assert first.skipped_ambiguous == 2
    assert second.seeded == 0
    assert second.existing == 1
    listing = ChannelListing.objects.get(source_listing_draft=draft)
    assert listing.channel == ChannelListing.Channel.EBAY
    assert ChannelListing.objects.filter(item=ambiguous_item).count() == 0


def test_manual_channel_listing_add_and_mark_ended_round_trip(api_client, category):
    item = make_item(category)
    listed_at = timezone.now().isoformat()

    create = api_client.post(
        "/api/channel-listings/",
        {
            "item": str(item.id),
            "channel": ChannelListing.Channel.FACEBOOK_MARKETPLACE,
            "listed_at": listed_at,
            "url": "https://example.invalid/listing",
            "note": "Manually listed",
        },
        format="json",
    )
    assert create.status_code == 201, create.data
    assert create.data["active"] is True
    assert create.data["channel_label"] == "Facebook"

    end = api_client.post(f"/api/channel-listings/{create.data['id']}/mark-ended/", {}, format="json")
    assert end.status_code == 200, end.data
    assert end.data["active"] is False
    assert end.data["ended_at"] is not None


def test_take_down_checklist_persists_until_every_active_row_is_ticked(api_client, category):
    item = make_item(category, quantity_total=1)
    facebook = ChannelListing.objects.create(
        item=item,
        channel=ChannelListing.Channel.FACEBOOK_MARKETPLACE,
        listed_at=timezone.now() - timedelta(days=3),
    )
    gumtree = ChannelListing.objects.create(
        item=item,
        channel=ChannelListing.Channel.GUMTREE,
        listed_at=timezone.now() - timedelta(days=2),
    )
    SaleRecord.objects.create(
        item=item,
        sale_date=timezone.localdate(),
        quantity=1,
        sale_price=Decimal("100.00"),
        actual_fees_total=Decimal("0.00"),
    )

    board = api_client.get("/api/channel-listings/board/")
    assert board.status_code == 200, board.data
    assert board.data["take_down_checklist"][0]["message"] == "Still listed on: Facebook, Gumtree - take them down."

    api_client.post(f"/api/channel-listings/{facebook.id}/mark-ended/", {}, format="json")
    board_after_one = api_client.get("/api/channel-listings/board/")
    assert board_after_one.data["take_down_checklist"][0]["message"] == "Still listed on: Gumtree - take them down."

    api_client.post(f"/api/channel-listings/{gumtree.id}/mark-ended/", {}, format="json")
    board_after_all = api_client.get("/api/channel-listings/board/")
    assert board_after_all.data["take_down_checklist"] == []


def test_partial_quantity_listing_stays_valid_until_remaining_hits_zero(api_client, category):
    item = make_item(category, quantity_total=2)
    ChannelListing.objects.create(
        item=item,
        channel=ChannelListing.Channel.FACEBOOK_MARKETPLACE,
        listed_at=timezone.now(),
    )
    SaleRecord.objects.create(
        item=item,
        sale_date=timezone.localdate(),
        quantity=1,
        sale_price=Decimal("50.00"),
        actual_fees_total=Decimal("0.00"),
    )

    board = api_client.get("/api/channel-listings/board/")

    assert board.status_code == 200, board.data
    assert board.data["take_down_checklist"] == []
    assert board.data["partial_quantity"][0]["message"] == "sold 1 of 2 - listings still valid."


def test_cash_lock_uses_active_channel_listing_before_legacy_draft_fallback(api_client, setting, category):
    today = timezone.now()
    active = make_item(category, title="Active channel listing", acquisition_cost=Decimal("40.00"))
    ended = make_item(category, title="Ended local listing", acquisition_cost=Decimal("30.00"))
    fallback = make_item(category, title="Legacy draft fallback", acquisition_cost=Decimal("20.00"))
    ChannelListing.objects.create(
        item=active,
        channel=ChannelListing.Channel.GUMTREE,
        listed_at=today - timedelta(days=95),
    )
    ChannelListing.objects.create(
        item=ended,
        channel=ChannelListing.Channel.FACEBOOK_MARKETPLACE,
        listed_at=today - timedelta(days=95),
        ended_at=today - timedelta(days=5),
    )
    ListingDraft.objects.create(
        item=ended,
        status=ListingDraft.Status.PUBLISHED,
        channel_data={"listing_id": "OLD-ENDED", "published_at": (today - timedelta(days=95)).date().isoformat()},
    )
    ListingDraft.objects.create(
        item=fallback,
        status=ListingDraft.Status.PUBLISHED,
        channel_data={"listing_id": "OLD-FALLBACK", "published_at": (today - timedelta(days=10)).date().isoformat()},
    )

    response = api_client.get("/api/profit/ledger/", {"stale_days": "90"})

    assert response.status_code == 200, response.data
    buckets = {bucket["id"]: bucket for bucket in response.data["cash_lock"]["buckets"]}
    by_title = {
        item["title"]: (bucket["id"], item)
        for bucket in response.data["cash_lock"]["buckets"]
        for item in bucket["items"]
    }
    assert by_title["Active channel listing"][0] == "listed_stale"
    assert by_title["Active channel listing"][1]["listed_date_basis"] == "active_channel_listing"
    assert by_title["Ended local listing"][0] == "unlisted"
    assert by_title["Ended local listing"][1]["listed_date_basis"] == "channel_listing_records_all_ended"
    assert by_title["Legacy draft fallback"][0] == "listed_fresh"
    assert by_title["Legacy draft fallback"][1]["listed_date_basis"] == "published_at"
    assert buckets["listed_stale"]["cash_locked"] == "40.00"


def test_sprint22_paths_have_no_auto_posting_or_new_network_calls():
    import apps.inventory.views as inventory_views
    import apps.listing.views as listing_views

    channel_source = inspect.getsource(channel_listings)
    copy_source = inspect.getsource(copy_packs)
    view_source = inspect.getsource(listing_views.ChannelListingViewSet)
    inventory_export_source = inspect.getsource(inventory_views.display_photo_export_key)
    for source in [channel_source, copy_source, view_source, inventory_export_source]:
        lowered = source.lower()
        for token in ["requests", "httpx", "urlopen", "urllib.request", "openai", "facebook-sdk"]:
            assert token not in lowered
    assert "apps.ebay" not in channel_source
    assert "publish_draft" not in view_source
    assert "stage_draft" not in view_source
