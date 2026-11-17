from copy import deepcopy
from datetime import timedelta

import pytest
from django.apps import apps
from django.utils import timezone
from rest_framework.test import APIClient

import integrations.ebay as ebay
from apps.ebay.review import eps_checks
from apps.listing.models import ChannelListing, ListingDraft
from apps.ebay.tests.test_sprint7 import ebay_settings, category, item, user, api_client, credential


pytestmark = pytest.mark.django_db


def owned_state():
    return {model._meta.label: list(model.objects.order_by("pk").values())
            for model in apps.get_models() if model._meta.managed}


def test_hub_is_authenticated_and_get_only(api_client):
    assert APIClient().get("/api/ebay/hub/").status_code in (401, 403)
    assert api_client.post("/api/ebay/hub/", {}, format="json").status_code == 405


def test_hub_reads_owned_history_and_active_drafts_without_writes_or_external_calls(api_client, item, credential, monkeypatch):
    published = ListingDraft.objects.create(item=item, status="published", title="Published nugget",
        channel_data={"listing_id": "listing-1", "offer_id": "offer-1", "secret": "must-not-return"})
    live = ChannelListing.objects.create(item=item, channel="ebay", external_listing_id="listing-1", source_listing_draft=published)
    active = ListingDraft.objects.create(item=item, status="publish_unknown", title="New draft",
        channel_data={"offer_id": "offer-2"}, publish_error={"message": "must-not-return"})
    def forbidden(*args, **kwargs):
        raise AssertionError("Hub must never call an external adapter, refresh or reconcile")
    for name in ["get_ebay_inventory_adapter", "get_ebay_account_adapter", "get_ebay_taxonomy_adapter", "get_ebay_media_adapter"]:
        monkeypatch.setattr(ebay, name, forbidden)
    monkeypatch.setattr("apps.ebay.services.get_access_token", forbidden)
    monkeypatch.setattr("apps.ebay.publish_state.recover_stale", forbidden)
    before = owned_state()
    response = api_client.get("/api/ebay/hub/")
    assert response.status_code == 200
    assert owned_state() == before
    payload = response.json()
    assert "not a live eBay check" in payload["provenance"]
    assert {row["id"] for row in payload["drafts"]} == {str(active.pk), str(published.pk)}
    assert payload["listings"][0]["id"] == str(live.pk)
    assert payload["listings"][0]["draft_id"] == str(published.pk)
    assert payload["listings"][0]["listing_id"] == "listing-1"
    assert "must-not-return" not in response.content.decode()
    assert "refresh-token" not in response.content.decode() and "access-token" not in response.content.decode()
    assert payload["connection"]["connected"] is True
    assert payload["connection"]["policies_fetched_at"] is None
    assert payload["orders"] == {"last_synced_at": None, "pending": 0, "duplicates": 0}


@pytest.mark.parametrize("reason", ["unknown upload time", "expired", "missing"])
def test_photo_freshness_names_only_actual_reason(item, reason):
    draft = ListingDraft.objects.create(item=item)
    now = timezone.now()
    photo = {"id": "own-photo", "sha256": "owned-image"}
    record = {"photo_id": photo["id"], "sha256": photo["sha256"], "url": "fake-eps://own", "uploaded_at": now.isoformat()}
    if reason == "expired":
        record["uploaded_at"] = (now - timedelta(days=31)).isoformat()
    elif reason == "unknown upload time":
        record.pop("uploaded_at")
    else:
        record["missing"] = True
    draft.channel_data = {"eps_photos": [record]}
    before = deepcopy(draft.channel_data)
    result = eps_checks(draft, [photo], now=now)
    assert len(result) == 1 and result[0]["field"] == "staging"
    assert f"{reason}: 1" in result[0]["message"]
    assert all(other not in result[0]["message"] for other in {"expired", "missing", "unknown upload time"} - {reason})
    assert draft.channel_data == before


def test_mixed_photo_reasons_are_counted_once_each(item):
    draft = ListingDraft.objects.create(item=item)
    now = timezone.now()
    photos = [{"id": str(i), "sha256": "own"} for i in range(3)]
    draft.channel_data = {"eps_photos": [
        {"photo_id": "1", "sha256": "own", "url": "fake-eps://1", "uploaded_at": (now-timedelta(days=31)).isoformat()},
        {"photo_id": "2", "sha256": "own", "url": "fake-eps://2", "uploaded_at": now.isoformat(), "missing": True},
    ]}
    message = eps_checks(draft, photos, now=now)[0]["message"]
    assert message.startswith("3 photos need re-uploading")
    for reason in ["expired", "missing", "unknown upload time"]:
        assert f"{reason}: 1" in message
