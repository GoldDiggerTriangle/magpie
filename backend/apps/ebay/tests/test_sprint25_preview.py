from copy import deepcopy
from datetime import timedelta

import pytest
from django.utils import timezone

import integrations.ebay as ebay
from apps.core.management.commands.seed import Command
from apps.ebay import publish_state
from apps.ebay.review import eps_checks, live_validation, photo_state, prepare_review
from apps.ebay.staging import stage_draft
from apps.ebay.workflow_errors import WorkflowError
from apps.listing.copy_packs import render_copy_pack
from apps.listing.editor import description_default
from apps.listing.models import ListingBoilerplate, ListingDraft
from apps.ebay.tests.test_sprint7 import ebay_settings, credential, merchant_location, item, category
from apps.ebay.tests.test_sprint25_publish import draft, stage


pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.parametrize("operation", ["stage", "publish"])
@pytest.mark.parametrize("field,value", [
    ("title", "Local pLaCeHoLdEr title"), ("subtitle", "PLACEHOLDER"),
    ("description_html", "<h2>PLACE<span>HOLDER</span></h2>"),
    ("est_shipping_note", "placeholder terms"),
    ("item_specifics", [{"name": "Metal", "value": "PLACEHOLDER"}]),
    ("item_specifics", [{"name": "PLACEHOLDER", "value": "Gold"}]),
])
def test_placeholder_blocks_stage_and_publish_with_named_field_without_provider_write(draft, operation, field, value):
    if operation == "publish":
        draft = stage(draft)
    review = prepare_review(draft)
    # Even an out-of-band edit with no revision bump must hit the local text gate.
    ListingDraft.objects.filter(pk=draft.pk).update(**{field: value})
    before = {name: getattr(ebay.FakeEbayInventoryAdapter, name) for name in ("create_count", "update_count", "publish_count")}
    with pytest.raises(WorkflowError) as error:
        if operation == "stage":
            stage_draft(draft, review_id=review.pk)
        else:
            publish_state.publish_draft(draft, review_id=review.pk, confirm_sku=draft.item.sku)
    issues = error.value.payload()["checks"]
    assert any(row["key"] == f"placeholder:{field}" and row["field"] == field and "PLACEHOLDER" in row["message"] for row in issues)
    assert {name: getattr(ebay.FakeEbayInventoryAdapter, name) for name in before} == before


def test_placeholder_preview_is_named_once_and_survives_unavailable_metadata(draft, monkeypatch):
    draft.description_html = "<p>place&#104;older terms</p>"
    draft.save()
    result = live_validation(draft)
    assert sum(row["key"] == "placeholder:description_html" for row in result["checks"]) == 1
    preview = prepare_review(draft).snapshot
    assert not preview["can_stage"] and not preview["can_publish"]
    monkeypatch.setattr(ebay, "get_ebay_inventory_adapter", lambda: (_ for _ in ()).throw(TimeoutError()))
    assert any(row["key"] == "placeholder:description_html" for row in live_validation(draft)["checks"])


def test_new_defaults_have_no_policy_placeholder_and_do_not_rewrite_drafts(draft):
    original = deepcopy(ListingDraft.objects.values().get(pk=draft.pk))
    Command().seed_listing({"Seed/example phone - Samsung Galaxy S21": draft.item})
    assert all("placeholder" not in row.body_html.casefold() for row in ListingBoilerplate.objects.all())
    assert "placeholder" not in description_default(draft.item).casefold()
    assert "placeholder" not in render_copy_pack(draft.item, channel="ebay")["sections"]["description"].casefold()
    assert ListingDraft.objects.values().get(pk=draft.pk) == original


def test_photo_reupload_blocker_counts_all_six_and_points_to_update_step(draft):
    photo = photo_state(draft)[0][0]
    photos = [{**photo, "id": f"photo-{index}"} for index in range(6)]
    result = eps_checks(draft, photos)
    assert len(result) == 1
    assert result[0]["message"].startswith("6 photos need re-uploading")
    assert result[0]["field"] == "staging"
    now = timezone.now()
    draft.channel_data["eps_photos"] = [{"photo_id": p["id"], "sha256": p["sha256"], "uploaded_at": (now-timedelta(days=1)).isoformat(), "url": "fake-eps://owned"} for p in photos]
    assert eps_checks(draft, photos, now=now) == []
    assert len(eps_checks(draft, photos, now=now+timedelta(days=31))) == 1
    assert eps_checks(draft, photos[:1], now=now+timedelta(days=31))[0]["message"].startswith("1 photo needs")
    blockers = {row["key"]: row for row in live_validation(draft)["publish_checks"]}
    assert blockers["staged_drift"]["field"] == "staging"
