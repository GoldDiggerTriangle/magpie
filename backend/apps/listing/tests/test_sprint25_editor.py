from copy import deepcopy
from datetime import timedelta
from decimal import Decimal
import json

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.catalog.models import ProductCategory
from apps.ebay.models import EbayAccountSnapshot, MerchantLocation
from apps.inventory.models import InventoryItem
from apps.listing import editor_metadata
from apps.listing.editor import editor_context, staged_changes
from apps.listing.models import ListingDraft
from apps.photos.models import PhotoAsset
from apps.research.models import Comparable


pytestmark = pytest.mark.django_db


@pytest.fixture
def api(django_user_model):
    client = APIClient()
    client.force_authenticate(django_user_model.objects.create_user(username="local-editor"))
    return client


@pytest.fixture
def listing():
    category = ProductCategory.objects.create(name="Editor gold", slug="editor-gold", sku_prefix="EG", profile_key="gold")
    item = InventoryItem.objects.create(title="Own Australian gold nugget", category=category, target_price=Decimal("360"), status="ready_to_list")
    photo = PhotoAsset.objects.create(item=item, original_path="own/original.jpg", processed_path="own/processed.jpg")
    now = timezone.now()
    EbayAccountSnapshot.objects.create(environment="sandbox", fetched_at=now,
        payment_policies=[{"paymentPolicyId": "p1", "name": "Payments", "marketplaceId": "EBAY_AU", "immediatePay": True}],
        fulfillment_policies=[{"fulfillmentPolicyId": "f4", "name": "Tracked", "marketplaceId": "EBAY_AU", "handlingTime": {"value": 2, "unit": "DAY"}, "shippingOptions": [{"optionType": "DOMESTIC", "shippingServices": [{"shippingServiceCode": "AU_AustraliaPostParcel", "shippingCost": {"value": "12.50", "currency": "AUD"}}]}]}],
        return_policies=[{"returnPolicyId": "r5", "name": "Returns", "marketplaceId": "EBAY_AU", "returnsAccepted": True, "returnPeriod": {"value": 30, "unit": "DAY"}, "returnShippingCostPayer": "BUYER"}])
    MerchantLocation.objects.create(environment="sandbox", merchant_location_key="MARYBOROUGH-AU", name="Maryborough", country="AU", city="Maryborough", state="VIC", postal_code="3465", created_on_ebay=True, fetched_at=now)
    metadata = {"category": {"category_id": "139965", "category_name": "Nugget", "is_leaf": True}, "aspects": [{"name": "Metal", "required": True, "values": ["Gold"]}, {"name": "Year", "required": False, "values": []}], "condition_policy": {"required": False, "conditions": []}, "listing_types": {"formats": {"FIXED_PRICE_ITEM": ["GTC"], "AUCTION": ["DAYS_7"]}}, "fetched_at": now.isoformat(), "provenance": "eBay metadata GET fixture"}
    return ListingDraft.objects.create(item=item, title=item.title, description_html="<p>Own nugget pictured.</p>", price=Decimal("360"), photo_ids=[str(photo.id)], item_specifics=[{"name": "Metal", "value": "Gold"}], channel_data={"category_id": "139965", "category_name": "Nugget", "condition_id": "", "listing_duration": "GTC", "payment_policy_id": "p1", "fulfillment_policy_id": "f4", "return_policy_id": "r5", "merchant_location_key": "MARYBOROUGH-AU", "editor_metadata": {"categories": {"139965": metadata}}}, generated_meta={"price_source": {"kind": "human_asking", "value": "360.00", "currency": "AUD", "label": "Human asking price"}})


def save(api, listing, **fields):
    listing.refresh_from_db()
    return api.patch(f"/api/listing-drafts/{listing.pk}/", {"editor_save": True, "expected_updated_at": listing.updated_at.isoformat(), **fields}, format="json")


def test_all_editor_fields_save_and_resume_without_network(api, listing, monkeypatch):
    monkeypatch.setattr(editor_metadata, "get_app_access_token", lambda: pytest.fail("Opening/saving must be offline"))
    photo2 = PhotoAsset.objects.create(item=listing.item, original_path="own/second.jpg", processed_path="own/second-display.jpg")
    channel = deepcopy(listing.channel_data)
    channel.update(listing_duration="DAYS_7", condition_id="", category_tree_id="15")
    title = "Australian Gold Nugget 1.4g - own specimen, natural surface"
    payload = dict(title=title, subtitle="Human subtitle", description_html="<p>My editable copy.</p>", listing_format="auction", price="365.00", currency="AUD", quantity=1, photo_ids=[str(photo2.id), *listing.photo_ids], item_specifics=[{"name": "Metal", "value": "Gold"}, {"name": "Weight", "value": "1.4g"}], est_shipping_note="Tracked parcel", include_sku_footer=True, boilerplate=None, channel_data=channel, price_choice={"kind": "human_asking"})
    response = save(api, listing, **payload)
    assert response.status_code == 200, response.data
    resumed = api.get(f"/api/listing-drafts/{listing.pk}/").data
    for key, value in payload.items():
        if key not in {"price_choice", "channel_data"}:
            assert resumed[key] == value
    assert resumed["channel_data"]["listing_duration"] == "DAYS_7"
    assert resumed["generated_meta"]["price_source"]["kind"] == "human_asking"
    assert resumed["generated_meta"]["editor_sources"]["title"] == "Human edit in listing editor"
    assert api.get(f"/api/listing-drafts/{listing.pk}/editor/").status_code == 200
    assert resumed["status"] == "draft"


def test_conditionless_category_and_recommended_aspects_never_block(listing):
    checks = editor_context(listing)["checks"]
    assert not [row for row in checks if row["level"] == "fail"]
    assert next(row for row in checks if row["key"] == "aspect:Year")["level"] == "warn"
    listing.channel_data["condition_id"] = "3000"
    assert not [row for row in editor_context(listing)["checks"] if row["key"] == "ebay_condition" and row["level"] == "fail"]
    listing.item_specifics = []
    assert next(row for row in editor_context(listing)["checks"] if row["key"] == "aspect:Metal")["level"] == "fail"


def test_required_condition_and_format_duration_are_validated(listing):
    cat = listing.channel_data["editor_metadata"]["categories"]["139965"]
    cat["condition_policy"] = {"required": True, "conditions": [{"conditionId": "3000", "conditionDescription": "Used"}]}
    assert any(row["key"] == "ebay_condition" and row["level"] == "fail" for row in editor_context(listing)["checks"])
    listing.channel_data["condition_id"] = "3000"
    listing.listing_format = "auction"
    assert any(row["key"] == "listing_duration" and row["level"] == "fail" for row in editor_context(listing)["checks"])
    listing.channel_data["listing_duration"] = "DAYS_7"
    assert not [row for row in editor_context(listing)["checks"] if row["level"] == "fail"]


def test_policy_options_are_real_terms_not_names_only(listing):
    policies = editor_context(listing)["metadata"]["policies"]
    postage = policies["fulfillment"][0]
    assert "$12.50" in postage["summary"] and "2 day" in postage["summary"]
    assert "Australia Post" in postage["summary"]
    assert "30 day" in policies["return"][0]["summary"] and "BUYER" in policies["return"][0]["summary"]
    assert "Immediate payment required" in policies["payment"][0]["summary"]
    assert all(row["fetched_at"] and row["provenance"] for group in policies.values() for row in group)
    assert "not recorded" in editor_metadata.policy_terms("fulfillment", {})[0]


def test_readiness_names_every_blocker_and_jump_target(listing):
    listing.title = listing.description_html = ""
    listing.price = None
    listing.photo_ids = []
    listing.channel_data = {}
    checks = editor_context(listing)["checks"]
    failed = {row["key"] for row in checks if row["level"] == "fail"}
    assert {"title_missing", "description_missing", "price_invalid", "no_photos", "ebay_category", "condition_metadata", "aspects_metadata", "payment_policy", "fulfillment_policy", "return_policy", "merchant_location", "listing_duration", "price_source"} <= failed
    assert all(row["field"] for row in checks)


def test_price_requires_explicit_d129_choice_and_never_uses_valuation(api, listing):
    response = save(api, listing, price="999.00")
    assert response.status_code == 400
    assert listing.price == Decimal("360.00")
    assert save(api, listing, price="999.00", price_choice={"kind": "ai"}).status_code == 400
    assert save(api, listing, price_choice={"kind": "owned_evidence", "id": "item_asking"}).status_code == 200
    listing.refresh_from_db()
    assert listing.price == listing.item.target_price
    assert listing.generated_meta["price_source"]["kind"] == "owned_evidence"


def test_unknown_currency_and_unrelated_evidence_cannot_be_chosen(api, listing):
    unknown = Comparable.objects.create(item=listing.item, kind="sold", price="123.00", price_basis="unknown")
    known = Comparable.objects.create(item=listing.item, kind="sold", price="120.00", price_basis="seller_receives")
    other_currency = Comparable.objects.create(item=listing.item, kind="sold", price="10.00", price_basis="seller_receives", currency="USD")
    unrelated = Comparable.objects.create(kind="sold", price="4.00", price_basis="seller_receives")
    options = editor_context(listing)["price_options"]
    assert {row["id"] for row in options} == {"item_asking", f"comp:{known.pk}"}
    for comp in [unknown, other_currency, unrelated]:
        assert save(api, listing, price_choice={"kind": "owned_evidence", "id": f"comp:{comp.pk}"}).status_code == 400
    assert save(api, listing, price_choice={"kind": "owned_evidence", "id": f"comp:{known.pk}"}).status_code == 200


def test_staged_edits_only_local_and_reserved_snapshot_not_client_writable(api, listing, monkeypatch):
    listing.status = "staged"
    listing.channel_data.update(offer_id="fixture-unpublished-offer", last_payload_snapshot={"offer": {"categoryId": "139965"}})
    listing.save()
    from apps.ebay import staging, publishing
    monkeypatch.setattr(staging, "stage_draft", lambda *a, **k: pytest.fail("No re-stage"))
    monkeypatch.setattr(publishing, "publish_draft", lambda *a, **k: pytest.fail("No publish"))
    old = deepcopy(listing.channel_data)
    attempted = {**old, "offer_id": "forged", "last_payload_snapshot": {}, "editor_metadata": {}}
    response = save(api, listing, title="Human change after staging", channel_data=attempted)
    assert response.status_code == 200
    listing.refresh_from_db()
    assert listing.status == "staged" and listing.channel_data["offer_id"] == old["offer_id"]
    assert listing.channel_data["last_payload_snapshot"] == old["last_payload_snapshot"]
    assert listing.channel_data["editor_metadata"] == old["editor_metadata"]
    assert staged_changes(listing)
    assert api.get(f"/api/listing-drafts/{listing.pk}/editor/").data["staged_local_changes"] is True


def test_preexisting_local_edits_are_compared_with_saved_staging_payload(listing):
    listing.channel_data.update(offer_id="isolated-offer", last_payload_snapshot={"inventory_item": {"product": {"title": listing.title}}, "offer": {"pricingSummary": {"price": {"value": "360.00", "currency": "AUD"}}}})
    assert not staged_changes(listing)
    listing.title = "Changed since the older staging snapshot"
    assert staged_changes(listing)


@pytest.mark.parametrize("fields", [{"channel_data": ["category_id"]}, {"item_specifics": "bad"}, {"item_specifics": [{"name": {}, "value": []}]}])
def test_malformed_editor_json_returns_field_error_not_server_error(api, listing, fields):
    assert save(api, listing, **fields).status_code == 400


def test_stale_save_is_conflict_not_truncated_or_overwritten(api, listing):
    old = listing.updated_at.isoformat()
    assert save(api, listing, title="Full human title that must remain intact").status_code == 200
    response = api.patch(f"/api/listing-drafts/{listing.pk}/", {"editor_save": True, "expected_updated_at": old, "title": "Old fragment"}, format="json")
    assert response.status_code == 409
    listing.refresh_from_db()
    assert listing.title == "Full human title that must remain intact"


@pytest.mark.parametrize("status", ["published", "archived", "publishing", "publish_unknown"])
def test_history_and_inflight_are_not_editor_writable(api, listing, status):
    listing.status = status
    listing.save()
    assert save(api, listing, title="Must not apply").status_code == 400


def test_explicit_refresh_uses_metadata_get_ports_only_and_never_selects(api, listing, monkeypatch):
    from integrations.ebay import FakeEbayTaxonomyAdapter
    calls = []
    adapter = FakeEbayTaxonomyAdapter()
    monkeypatch.setattr(editor_metadata, "get_app_access_token", lambda: "isolated-fake-token")
    monkeypatch.setattr(editor_metadata.ebay, "get_ebay_taxonomy_adapter", lambda **kwargs: adapter)
    monkeypatch.setattr(editor_metadata, "refresh_account_snapshot", lambda **kwargs: calls.append("account-policy-GETs"))
    old_fields = (listing.title, listing.price, listing.channel_data["category_id"])
    result = api.post(f"/api/listing-drafts/{listing.pk}/refresh-metadata/", {"category_id": "139965"}, format="json")
    assert result.status_code == 200, result.data
    listing.refresh_from_db()
    assert (listing.title, listing.price, listing.channel_data["category_id"]) == old_fields
    assert calls == ["account-policy-GETs"]
    assert result.data["editor"]["metadata"]["category_snapshot"]["listing_types"]["formats"]["FIXED_PRICE_ITEM"] == ["GTC"]
    assert listing.channel_data.get("offer_id") is None
    assert b"isolated-fake-token" not in result.content


def test_refresh_failure_preserves_cached_snapshot_and_is_secret_free(api, listing, monkeypatch):
    from integrations.ebay import EbayUnavailable
    before = deepcopy(listing.channel_data)
    def unavailable():
        raise EbayUnavailable("DO-NOT-EXPOSE-THIS-PAYLOAD")
    monkeypatch.setattr(editor_metadata, "get_app_access_token", unavailable)
    result = api.post(f"/api/listing-drafts/{listing.pk}/refresh-metadata/", {}, format="json")
    assert result.status_code == 503
    assert "DO-NOT-EXPOSE" not in json.dumps(result.data)
    listing.refresh_from_db()
    assert listing.channel_data == before


def test_loading_cached_metadata_has_no_writes(api, listing, monkeypatch):
    before = (listing.updated_at, deepcopy(listing.channel_data))
    monkeypatch.setattr(editor_metadata, "get_app_access_token", lambda: pytest.fail("No automatic remote GET"))
    assert api.get(f"/api/listing-drafts/{listing.pk}/editor/").status_code == 200
    listing.refresh_from_db()
    assert (listing.updated_at, listing.channel_data) == before


@pytest.mark.parametrize("key,value", [
    ("category_id", "105848"), ("category_name", "Australian Stamps"), ("category_tree_id", "15"),
    ("condition_id", "3000"), ("listing_duration", "DAYS_7"), ("payment_policy_id", "other-payment"),
    ("fulfillment_policy_id", "other-postage"), ("return_policy_id", "other-return"),
    ("merchant_location_key", "OTHER-LOCATION"),
])
def test_each_channel_field_round_trips_without_selecting_other_values(api, listing, key, value):
    before = deepcopy(listing.channel_data)
    result = save(api, listing, channel_data={key: value})
    assert result.status_code == 200
    resumed = api.get(f"/api/listing-drafts/{listing.pk}/").data
    assert resumed["channel_data"][key] == value
    assert {k: v for k, v in resumed["channel_data"].items() if k != key} == {k: v for k, v in before.items() if k != key}


def test_listing_duration_adapter_uses_category_filtered_metadata_get(monkeypatch):
    from apps.ebay import adapters
    calls = []
    def response(url, **kwargs):
        calls.append((url, kwargs["method"]))
        return {"listingTypePolicies": [{"categoryId": "139965", "listingDurations": [
            {"listingType": "FIXED_PRICE_ITEM", "durationValues": ["GTC"]},
            {"listingType": "AUCTION", "durationValues": ["DAYS_7"]},
        ]}]}
    monkeypatch.setattr(adapters, "_request_json", response)
    adapter = adapters.HttpEbayTaxonomyAdapter(access_token="isolated-test-token", environment="production")
    policy = adapter.listing_type_policy(category_id="139965")
    assert policy["formats"] == {"FIXED_PRICE_ITEM": ["GTC"], "AUCTION": ["DAYS_7"]}
    assert calls == [("https://api.ebay.com/sell/metadata/v1/marketplace/EBAY_AU/get_listing_type_policies?filter=categoryIds%3A%7B139965%7D", "GET")]
