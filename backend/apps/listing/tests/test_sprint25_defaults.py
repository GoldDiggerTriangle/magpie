from copy import deepcopy
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.ebay.models import EbayAccountSnapshot, MerchantLocation
from apps.inventory.models import InventoryItem
from apps.listing.defaults import DEFAULT_FIELDS, apply_new_defaults, defaults_metadata, evaluate_defaults
from apps.listing.editor import editor_context
from apps.listing.export import listing_summary
from apps.listing.models import CategoryListingDefaults, ListingDraft
from apps.listing.tests.test_sprint25_editor import api, listing, save
from apps.sales.models import SaleRecord


pytestmark = pytest.mark.django_db


def values(listing):
    return {**{key: listing.channel_data.get(key, "") for key in DEFAULT_FIELDS if key != "listing_format"}, "listing_format": "fixed"}


def url(listing):
    return f"/api/listing-defaults/{listing.item.category_id}/"


def set_defaults(api, listing, data=None):
    data = values(listing) if data is None else data
    preview = api.post(url(listing) + "preview/", {"values": data}, format="json")
    assert preview.status_code == 200, preview.data
    result = api.put(url(listing), {"values": preview.data["values"], "expected_revision": preview.data["expected_revision"]}, format="json")
    assert result.status_code == 200, result.data
    return result


def new_item(listing, **fields):
    return InventoryItem.objects.create(category=listing.item.category, title="Own new nugget", **fields)


def create(api, item):
    response = api.post(f"/api/items/{item.pk}/listing-drafts/", {}, format="json")
    assert response.status_code == 201, response.data
    return ListingDraft.objects.get(pk=response.data["id"])


def test_defaults_fill_only_new_drafts_with_persistent_sources_never_price(api, listing, monkeypatch):
    import integrations.ebay as ebay
    for name in ("get_ebay_taxonomy_adapter", "get_ebay_inventory_adapter", "get_ebay_auth_adapter"):
        monkeypatch.setattr(ebay, name, lambda **kw: pytest.fail("Creation is offline"))
    set_defaults(api, listing)
    item = new_item(listing, target_price="999.00", quantity_total=5)
    SaleRecord.objects.create(item=item, sale_date=timezone.localdate(), sale_price="40", quantity=2)
    row = create(api, item)
    assert row.quantity == 3 and row.price is None and row.listing_format == "fixed"
    assert row.channel_data["category_id"] == "139965" and row.channel_data["payment_policy_id"] == "p1"
    sources = editor_context(row)["sources"]
    assert sources["category_id"] == sources["listing_format"] == "from Editor gold defaults"
    assert sources["quantity"] == "Item remaining stock (total minus sold)"
    assert listing_summary(row, [], [])["generated_meta"]["editor_sources"] == row.generated_meta["editor_sources"]
    assert api.get(f"/api/listing-drafts/{row.pk}/editor/").data["sources"]["category_id"] == sources["category_id"]
    before = ListingDraft.objects.values().get(pk=row.pk)
    set_defaults(api, listing, {})
    reopened = api.post(f"/api/items/{item.pk}/listing-drafts/", {}, format="json")
    assert reopened.status_code == 200 and reopened.data["id"] == str(row.pk)
    assert ListingDraft.objects.values().get(pk=row.pk) == before


@pytest.mark.parametrize("field", ["price", "quantity", "item_specifics", "title", "description_html", "channel_data", "offer_id", "generated_meta", "unknown"])
def test_api_allowlist_rejects_every_non_d135_field(api, listing, field):
    for suffix in ("", "preview/"):
        response = (api.put if not suffix else api.post)(url(listing) + suffix, {"values": {field: "10"}, "expected_revision": "ignored"} if not suffix else {"values": {field: "10"}}, format="json")
        assert response.status_code == 400
    assert not CategoryListingDefaults.objects.exists()
    assert api.post(url(listing) + "preview/", {"values": {}, field: "10"}, format="json").status_code == 400


def test_no_defaults_leaves_defaultable_fields_empty_and_remaining_zero_honest(api, listing):
    row = create(api, new_item(listing, quantity_total=0))
    assert row.quantity == 0 and row.price is None and row.listing_format == ""
    assert not {key: row.channel_data.get(key) for key in DEFAULT_FIELDS if row.channel_data.get(key)}
    assert any(check["field"] == "listing_format" and check["level"] == "fail" for check in editor_context(row)["checks"])


def test_defaults_updates_never_change_published_or_existing_drafts(api, listing):
    before = list(ListingDraft.objects.values())
    set_defaults(api, listing)
    set_defaults(api, listing, {"listing_format": "auction"})
    assert list(ListingDraft.objects.values()) == before


def test_relist_uses_published_seed_not_defaults_and_remaining_stock(api, listing):
    set_defaults(api, listing, {"category_id": "999", "listing_format": "auction"})
    listing.status = "published"
    listing.save()
    before = ListingDraft.objects.values().get(pk=listing.pk)
    result = api.post(f"/api/items/{listing.item_id}/listing-drafts/", {}, format="json")
    assert result.status_code == 201
    row = ListingDraft.objects.get(pk=result.data["id"])
    assert row.channel_data["category_id"] == "139965" and row.listing_format == "fixed"
    assert row.price == listing.price and row.generated_meta["relisted_from"] == str(listing.pk)
    assert row.quantity == listing.item.quantity_remaining
    assert ListingDraft.objects.values().get(pk=listing.pk) == before


@pytest.mark.parametrize("field,mutate", [
    ("category_id", lambda cat: cat["category"].update(is_leaf=False)),
    ("condition_id", lambda cat: cat.update(condition_policy={"required": True, "conditions": [{"conditionId": "3000"}]})),
    ("listing_duration", lambda cat: cat["listing_types"]["formats"].update(FIXED_PRICE_ITEM=["DAYS_3"])),
    ("listing_format", lambda cat: cat["listing_types"]["formats"].pop("FIXED_PRICE_ITEM")),
])
def test_confirmed_invalid_defaults_empty_named_in_readiness(api, listing, field, mutate):
    data = values(listing)
    data["condition_id"] = "1000"
    set_defaults(api, listing, data)
    mutate(listing.channel_data["editor_metadata"]["categories"]["139965"])
    listing.save()
    row = create(api, new_item(listing))
    assert (row.listing_format if field == "listing_format" else row.channel_data.get(field)) in (None, "")
    assert any(check["key"] == f"default:{field}" and check["level"] == "fail" for check in editor_context(row)["checks"])
    if field == "category_id":
        assert not row.channel_data.get("condition_id")


@pytest.mark.parametrize("kind", ["payment", "fulfillment", "return"])
def test_policy_account_marketplace_and_category_applicability(api, listing, kind):
    set_defaults(api, listing)
    account = EbayAccountSnapshot.objects.get(environment="sandbox")
    rows = getattr(account, f"{kind}_policies")
    rows[0]["marketplaceId"] = "EBAY_US"
    account.save()
    row = create(api, new_item(listing))
    assert not row.channel_data.get(f"{kind}_policy_id")
    rows[0]["marketplaceId"] = "EBAY_AU"
    rows[0]["categoryTypes"] = [{"name": "MOTORS_VEHICLES"}]
    account.save()
    listing.channel_data["editor_metadata"]["categories"]["139965"]["category"]["policy_category_type"] = "ALL_EXCLUDING_MOTORS_VEHICLES"
    listing.channel_data["editor_metadata"]["categories"]["139965"]["fetched_at"] = timezone.now().isoformat()
    listing.save()
    row = create(api, new_item(listing))
    assert not row.channel_data.get(f"{kind}_policy_id")


def test_unverified_location_is_empty_but_missing_location_is_uncertain(api, listing):
    set_defaults(api, listing)
    location = MerchantLocation.objects.get(environment="sandbox")
    location.created_on_ebay = False
    location.save()
    row = create(api, new_item(listing))
    assert not row.channel_data.get("merchant_location_key")
    location.delete()
    row = create(api, new_item(listing))
    assert row.channel_data["merchant_location_key"] == "MARYBOROUGH-AU"
    assert any(c["field"] == "merchant_location_key" and c["state"] == "unchecked" for c in row.generated_meta["listing_defaults_review"])


def test_missing_incomplete_and_stale_metadata_are_not_invalid(api, listing):
    data = values(listing)
    data["condition_id"] = "3000"
    metadata, _ = defaults_metadata(data)
    metadata["category_snapshot"] = {"fetched_at": None, "condition_policy": {"conditions": []}}
    applied, checks = evaluate_defaults(data, metadata)
    assert applied == data
    assert {row["state"] for row in checks} == {"unchecked"}
    assert all("couldn't check" in row["message"] for row in checks)
    old = listing.channel_data["editor_metadata"]["categories"]["139965"]
    old["fetched_at"] = (timezone.now() - timedelta(days=20)).isoformat()
    listing.save()
    set_defaults(api, listing)
    row = create(api, new_item(listing))
    assert row.channel_data["category_id"] == "139965"
    assert editor_context(row)["metadata"]["category_stale"]


def test_latest_complete_snapshot_survives_newer_incomplete_snapshot(api, listing):
    partial = deepcopy(listing.channel_data["editor_metadata"]["categories"]["139965"])
    partial["listing_types"] = None
    partial["fetched_at"] = (timezone.now() + timedelta(minutes=1)).isoformat()
    CategoryListingDefaults.objects.create(category=listing.item.category, environment="sandbox", values=values(listing), metadata={"categories": {"139965": partial}})
    row = create(api, new_item(listing))
    assert row.channel_data["listing_duration"] == "GTC"
    assert row.channel_data["editor_metadata"]["categories"]["139965"]["listing_types"]


def test_conditionless_and_missing_default_category(api, listing):
    set_defaults(api, listing, {**values(listing), "condition_id": "3000"})
    row = create(api, new_item(listing))
    assert not row.channel_data.get("condition_id")
    assert not any(c["key"] == "default:condition_id" and c["level"] == "fail" for c in editor_context(row)["checks"])
    assert any(c["state"] == "not_used" for c in row.generated_meta["listing_defaults_review"])
    result = set_defaults(api, listing, {"condition_id": "3000"})
    assert not result.data["values"].get("condition_id")


def test_manual_edit_replaces_provenance_in_both_save_paths(api, listing):
    set_defaults(api, listing)
    row = create(api, new_item(listing))
    assert save(api, row, channel_data={"payment_policy_id": "human-choice"}).status_code == 200
    row.refresh_from_db()
    assert editor_context(row)["sources"]["payment_policy_id"] == "Human selection in listing editor"
    response = api.patch(f"/api/listing-drafts/{row.pk}/", {"listing_format": "auction"}, format="json")
    assert response.status_code == 200
    row.refresh_from_db()
    assert editor_context(row)["sources"]["listing_format"] == "Human edit in listing editor"
    assert editor_context(row)["sources"]["category_id"] == "from Editor gold defaults"


def test_preview_includes_clearing_is_read_only_and_revision_prevents_stale_save(api, listing):
    set_defaults(api, listing)
    before = list(CategoryListingDefaults.objects.values())
    preview = api.post(url(listing) + "preview/", {"values": {"listing_format": "auction"}}, format="json")
    assert preview.status_code == 200
    assert any(row["field"] == "category_id" and row["clears"] and row["after"] == "" for row in preview.data["changes"])
    assert list(CategoryListingDefaults.objects.values()) == before
    set_defaults(api, listing, {"listing_format": "fixed"})
    assert api.put(url(listing), {"values": preview.data["values"], "expected_revision": preview.data["expected_revision"]}, format="json").status_code == 409


def test_settings_gets_and_preview_do_not_create_rows_or_call_network(api, listing, monkeypatch):
    from apps.listing import editor_metadata
    monkeypatch.setattr(editor_metadata, "get_app_access_token", lambda: pytest.fail("Offline defaults"))
    assert api.get("/api/listing-defaults/").status_code == 200
    assert api.get(url(listing)).status_code == 200
    assert api.post(url(listing) + "preview/", {"values": values(listing)}, format="json").status_code == 200
    assert not CategoryListingDefaults.objects.exists()


def test_refresh_failure_preserves_values_and_last_complete_snapshot(api, listing, monkeypatch):
    from apps.listing import defaults_views
    from integrations.ebay import EbayUnavailable
    set_defaults(api, listing)
    before = list(CategoryListingDefaults.objects.values())
    def failed(**kwargs):
        raise EbayUnavailable("DO-NOT-EXPOSE-PROVIDER-PAYLOAD")
    monkeypatch.setattr(defaults_views, "fetch_editor_metadata", failed)
    response = api.post(url(listing) + "refresh-metadata/", {"category_id": "139965"}, format="json")
    assert response.status_code == 503
    assert b"DO-NOT-EXPOSE" not in response.content
    assert list(CategoryListingDefaults.objects.values()) == before


def test_nonleaf_refresh_can_confirm_invalidity_without_fetching_leaf_only_metadata(api, listing, monkeypatch):
    from apps.listing import editor_metadata
    from integrations.ebay import FakeEbayTaxonomyAdapter
    set_defaults(api, listing)
    adapter = FakeEbayTaxonomyAdapter()
    monkeypatch.setattr(adapter, "category_details", lambda **kw: {"category_id": "139965", "category_name": "Now a branch", "is_leaf": False})
    monkeypatch.setattr(adapter, "item_aspects", lambda **kw: pytest.fail("Non-leaf has no leaf metadata"))
    monkeypatch.setattr(editor_metadata, "get_app_access_token", lambda: "fake-only")
    monkeypatch.setattr(editor_metadata.ebay, "get_ebay_taxonomy_adapter", lambda **kw: adapter)
    monkeypatch.setattr(editor_metadata, "refresh_account_snapshot", lambda **kw: None)
    response = api.post(url(listing) + "refresh-metadata/", {"category_id": "139965"}, format="json")
    assert response.status_code == 200, response.data
    row = create(api, new_item(listing))
    assert not row.channel_data.get("category_id")
    assert any(c["key"] == "default:category_id" and c["level"] == "fail" for c in editor_context(row)["checks"])


def test_uncertain_creation_warning_clears_after_metadata_check_without_field_changes(api, listing):
    set_defaults(api, listing)
    account = EbayAccountSnapshot.objects.get(environment="sandbox")
    account.fetched_at = None
    account.save()
    row = create(api, new_item(listing))
    assert any(c["key"] == "default:payment_policy_id" for c in editor_context(row)["checks"])
    before = ListingDraft.objects.values().get(pk=row.pk)
    account.fetched_at = timezone.now()
    account.save()
    assert not any(c["key"] == "default:payment_policy_id" for c in editor_context(row)["checks"])
    assert ListingDraft.objects.values().get(pk=row.pk) == before


def test_creation_retains_choices_when_category_snapshot_is_unavailable(api, listing):
    set_defaults(api, listing, {**values(listing), "condition_id": "3000"})
    listing.channel_data["editor_metadata"] = {}
    listing.save()
    row = create(api, new_item(listing))
    assert row.channel_data["category_id"] == "139965"
    assert row.channel_data["condition_id"] == "3000"
    assert row.listing_format == "fixed" and row.channel_data["listing_duration"] == "GTC"
    checks = editor_context(row)["checks"]
    assert any(c["key"] == "default:category_id" and c["level"] == "warn" and "couldn't check" in c["message"] for c in checks)


def test_defaults_require_authenticated_session(listing):
    from rest_framework.test import APIClient
    client = APIClient()
    assert client.get(url(listing)).status_code in (401, 403)
    assert client.post(url(listing) + "preview/", {"values": {}}, format="json").status_code in (401, 403)
    assert not CategoryListingDefaults.objects.exists()


def test_confirmed_account_policy_opt_out_is_invalid(api, listing):
    set_defaults(api, listing)
    account = EbayAccountSnapshot.objects.get(environment="sandbox")
    account.business_policies_opted_in = False
    account.save()
    row = create(api, new_item(listing))
    assert all(not row.channel_data.get(f"{kind}_policy_id") for kind in ("payment", "fulfillment", "return"))


def test_snapshot_before_reconnect_is_uncertain_not_proof_of_invalidity(api, listing):
    from apps.ebay.models import EbayCredential
    set_defaults(api, listing)
    EbayCredential.objects.create(environment="sandbox", refresh_token="isolated-fixture-token")
    row = create(api, new_item(listing))
    assert row.channel_data["payment_policy_id"] == "p1"
    assert any(c["field"] == "payment_policy_id" and c["state"] == "unchecked" for c in row.generated_meta["listing_defaults_review"])


@pytest.mark.parametrize("part", ["condition_policy", "listing_types"])
def test_foreign_category_metadata_is_incomplete_not_invalid(listing, part):
    data = {**values(listing), "condition_id": "3000"}
    metadata, _ = defaults_metadata(data)
    metadata["category_snapshot"][part]["category_id"] = "different-category"
    applied, checks = evaluate_defaults(data, metadata)
    field = "condition_id" if part == "condition_policy" else "listing_duration"
    assert applied[field] == data[field]
    assert next(c for c in checks if c["field"] == field)["state"] == "unchecked"


def test_empty_format_cannot_silently_fall_through_to_auction(listing, monkeypatch):
    from django.core.exceptions import ValidationError
    from apps.ebay import staging
    from apps.listing.readiness import check_readiness
    listing.listing_format = ""
    monkeypatch.setattr(staging, "get_category_condition_policy", lambda **kw: pytest.fail("Guard must precede any metadata call"))
    with pytest.raises(ValidationError, match="empty format is not an auction"):
        staging._guard_stageable(listing)
    assert any(c.key == "listing_format" and c.level == "fail" for c in check_readiness(listing))


def test_manual_category_correction_removes_obsolete_default_condition_issue(api, listing):
    set_defaults(api, listing, {**values(listing), "condition_id": "3000"})
    listing.channel_data["editor_metadata"]["categories"]["139965"]["category"]["is_leaf"] = False
    listing.save()
    row = create(api, new_item(listing))
    assert any(c["field"] == "condition_id" and c["state"] == "invalid" for c in row.generated_meta["listing_defaults_review"])
    response = api.patch(f"/api/listing-drafts/{row.pk}/", {"channel_data": {"category_id": "105848", "category_name": "Australian Stamps", "category_tree_id": "15"}}, format="json")
    assert response.status_code == 200
    row.refresh_from_db()
    assert not any(c["field"] == "condition_id" for c in row.generated_meta["listing_defaults_review"])
