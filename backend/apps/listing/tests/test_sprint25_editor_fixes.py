from copy import deepcopy
from decimal import Decimal

import pytest

from .test_sprint25_editor import api, listing
from apps.audit.models import AuditLog
from apps.ebay import adapters
from apps.listing.editor import editor_context
from apps.listing.editor_metadata import policy_options
from apps.listing.models import ListingDraft

pytestmark = pytest.mark.django_db


def test_duration_is_recovered_read_only_from_staged_payload(api, listing):
    listing.channel_data.update(listing_duration="", last_payload_snapshot={"offer": {"categoryId": "139965", "format": "FIXED_PRICE", "listingDuration": "GTC"}})
    listing.save()
    before = deepcopy(listing.channel_data), listing.updated_at
    context = api.get(f"/api/listing-drafts/{listing.pk}/editor/").data
    assert context["effective_duration"] == "GTC"
    assert "Saved staged offer" in context["duration_source"]
    assert not [row for row in context["checks"] if row["key"] == "listing_duration" and row["level"] == "fail"]
    listing.refresh_from_db()
    assert (listing.channel_data, listing.updated_at) == before
    listing.listing_format = "auction"
    assert editor_context(listing)["effective_duration"] == ""


def test_explicit_duration_always_wins_over_saved_staged_offer(listing):
    listing.channel_data.update(listing_duration="DAYS_7", last_payload_snapshot={"offer": {"categoryId": "139965", "format": "FIXED_PRICE", "listingDuration": "GTC"}})
    assert editor_context(listing)["effective_duration"] == "DAYS_7"


@pytest.mark.parametrize("amount,expected", [("23.95", "$23.95"), ("0.0", "Free"), ("8", "$8.00")])
def test_policy_headline_and_real_terms_format_without_currency_noise(amount, expected):
    rows = policy_options("fulfillment", [{"fulfillmentPolicyId": "f1", "name": "Post", "shippingOptions": [{"optionType": "DOMESTIC", "shippingServices": [{"shippingServiceCode": "AU_AustraliaPostParcel", "shippingCost": {"value": amount, "currency": "AUD"}, "additionalShippingCost": {"value": "0.0", "currency": "AUD"}}]}]}], "2026-11-14T00:00:00Z")
    assert rows[0]["headline"] == expected
    assert rows[0]["terms"][0] == f"Domestic: Australia Post Parcel - {expected}"
    assert "AUD 0" not in str(rows) and "Additional item" not in str(rows)


def test_archive_retains_row_and_records_audit_and_rejects_delete(api, listing):
    assert api.delete(f"/api/listing-drafts/{listing.pk}/").status_code == 400
    before = ListingDraft.objects.count()
    from django.core.exceptions import ValidationError
    from django.db import transaction
    with pytest.raises(ValidationError):
        with transaction.atomic():
            listing.delete()
    result = api.post(f"/api/listing-drafts/{listing.pk}/archive/", {}, format="json")
    assert result.status_code == 200, result.data
    assert ListingDraft.objects.count() == before
    listing.refresh_from_db()
    assert listing.status == "archived"
    assert AuditLog.objects.filter(action="listing.draft.archived", target_id=str(listing.pk)).count() == 1
    assert api.patch(f"/api/listing-drafts/{listing.pk}/", {"title": "No rewrite"}, format="json").status_code == 400


def test_offer_blocks_archive_regardless_of_status_and_patch_cannot_bypass(api, listing):
    listing.channel_data["offer_id"] = "isolated-staged-offer"
    listing.save()
    before = listing.status, deepcopy(listing.channel_data), AuditLog.objects.count()
    assert api.post(f"/api/listing-drafts/{listing.pk}/archive/", {}, format="json").status_code == 400
    assert api.patch(f"/api/listing-drafts/{listing.pk}/", {"status": "archived"}, format="json").status_code == 400
    assert api.patch(f"/api/listing-drafts/{listing.pk}/", {"channel_data": {"offer_id": ""}}, format="json").status_code == 400
    listing.refresh_from_db()
    assert (listing.status, listing.channel_data, AuditLog.objects.count()) == before


def test_category_browse_gets_one_branch_and_discards_all_deeper_descendants(monkeypatch):
    calls = []
    def request(url, **kwargs):
        calls.append((url, kwargs["method"]))
        if "get_default_category_tree_id" in url:
            assert "marketplace_id=EBAY_AU" in url
            return {"categoryTreeId": "15"}
        return {"categorySubtreeNode": {"category": {"categoryId": "281", "categoryName": "Jewellery"}, "childCategoryTreeNodes": [{"category": {"categoryId": "10210", "categoryName": "Gold"}, "leafCategoryTreeNode": False, "childCategoryTreeNodes": [{"category": {"categoryId": "139965", "categoryName": "Nugget"}, "leafCategoryTreeNode": True}]}]}}
    monkeypatch.setattr(adapters, "_request_json", request)
    adapter = adapters.HttpEbayTaxonomyAdapter(access_token="isolated-token", environment="production")
    branch = adapter.category_children(category_id="281")
    assert len(calls) == 2 and all(method == "GET" for _, method in calls)
    assert "get_category_subtree?category_id=281" in calls[1][0]
    assert "139965" not in str(branch)
    assert branch["children"][0]["is_leaf"] is False
    assert "childCategoryTreeNodes" not in str(branch)
    with pytest.raises(adapters.EbayUnavailable):
        adapter.category_children(category_id="0")
    assert len(calls) == 2


def test_browse_endpoint_never_saves_draft(api, listing, monkeypatch):
    import integrations.ebay as ebay
    from apps.ebay import services
    monkeypatch.setattr(services, "get_app_access_token", lambda: "isolated-token")
    monkeypatch.setattr(ebay, "get_ebay_taxonomy_adapter", lambda **kwargs: adapters.FakeEbayTaxonomyAdapter())
    before = deepcopy(listing.channel_data), listing.updated_at
    result = api.get(f"/api/listing-drafts/{listing.pk}/category-children/?category_id=260")
    assert result.status_code == 200 and result.data["fetched_at"]
    listing.refresh_from_db()
    assert (listing.channel_data, listing.updated_at) == before
