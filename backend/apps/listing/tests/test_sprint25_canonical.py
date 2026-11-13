from datetime import timedelta
from decimal import Decimal
from io import StringIO
import json
from uuid import UUID

import pytest
from django.core.exceptions import ValidationError
from django.core.management import call_command, CommandError
from django.db import connection, transaction
from django.utils import timezone
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.catalog.models import ProductCategory
from apps.ebay.staging import stage_draft, withdraw_staged
from apps.inventory.models import InventoryItem
from apps.listing.canonical import (
    apply_migration_a, completeness_components, get_or_create_canonical_draft,
    migration_a_plan, plan_group,
)
from apps.listing.draft_status import DRAFT_STATUS_CLASSIFICATION, active_draft_filter, classify_draft_status
from apps.listing.models import ChannelListing, ListingDraft
from apps.listing.canonical_check import CONSTRAINT_NAME


pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def before_migration_b(db):
    # These are Migration A/legacy-duplicate tests, before B is installed.
    # Dropping this index inside the test transaction rolls back at teardown;
    # separate Migration B tests exercise the installed constraint on both lanes.
    assert connection.in_atomic_block
    constraint = next(row for row in ListingDraft._meta.constraints if row.name == CONSTRAINT_NAME)
    with connection.cursor() as cursor:
        cursor.execute(str(constraint.remove_sql(ListingDraft, connection.schema_editor())))


@pytest.fixture
def item():
    category = ProductCategory.objects.create(name="Canonical gold", slug="canonical-gold", sku_prefix="CG", profile_key="gold")
    return InventoryItem.objects.create(title="Own gold photo item", category=category)


@pytest.fixture
def api_client(django_user_model):
    user = django_user_model.objects.create_user(username="canonical-reviewer")
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def draft(item, **kwargs):
    return ListingDraft.objects.create(item=item, **kwargs)


def complete_data(*, required=True):
    return {
        "category_id": "139965", "category_tree_id": "15", "condition_id": "3000",
        "payment_policy_id": "p1", "fulfillment_policy_id": "f4", "return_policy_id": "r5",
        "merchant_location_key": "MARYBOROUGH-AU",
        "last_payload_snapshot": {
            "offer": {"categoryId": "139965"},
            "aspects": {
                "aspects": [{"name": "Metal", "required": required}],
                "fetched_at": "2026-11-13T06:00:00+00:00",
            },
        },
    }


def test_every_status_is_explicitly_classified_and_future_status_defaults_active(item):
    assert set(DRAFT_STATUS_CLASSIFICATION) == set(ListingDraft.Status.values)
    for value in ListingDraft.Status.values:
        row = draft(item, status=value)
        assert ListingDraft.objects.filter(pk=row.pk).filter(active_draft_filter()).exists() == (value not in {"published", "archived"})
    future = draft(item, status="future_status")
    assert classify_draft_status("future_status") == "active"
    assert ListingDraft.objects.filter(active_draft_filter(), pk=future.pk).exists()
    assert not any(field.name == "publish_state" for field in ListingDraft._meta.fields)


def test_score_is_ten_explicit_local_components_and_unknown_metadata_is_not_complete(item):
    row = draft(item, title="Own item", price=Decimal("360"), photo_ids=["own-photo"], channel_data=complete_data(), item_specifics=[{"name": "Metal", "value": "Gold"}])
    parts = completeness_components(row)
    assert len(parts) == 10
    assert sum(parts.values()) == 10
    row.item_specifics = []
    assert sum(completeness_components(row).values()) == 9
    row.channel_data.pop("last_payload_snapshot")
    assert completeness_components(row)["required_aspects"] is False
    row.channel_data = complete_data()
    row.channel_data["category_id"] = "different"
    assert completeness_components(row)["required_aspects"] is False


def test_conditionless_category_scores_complete_only_with_matching_cached_policy(item):
    data = complete_data(required=False)
    data["condition_id"] = ""
    data["last_payload_snapshot"]["condition_policy"] = {
        "category_id": "139965", "marketplace": "EBAY_AU", "required": False, "conditions": [],
        "fetched_at": "2026-11-13T06:00:00+00:00",
    }
    row = draft(item, channel_data=data)
    assert completeness_components(row)["condition"] is True
    assert completeness_components(row)["required_aspects"] is True
    row.channel_data["last_payload_snapshot"]["condition_policy"]["category_id"] = "other"
    assert completeness_components(row)["condition"] is False


def test_single_staged_offer_always_wins_and_four_other_drafts_are_planned_not_written(item):
    keeper = draft(item, status="staged", channel_data={"offer_id": "356038014011"})
    others = [draft(item, title=f"Other {i}", price=Decimal("400")) for i in range(4)]
    before = list(ListingDraft.objects.order_by("pk").values())
    plan = migration_a_plan()
    group = plan["groups"][0]
    assert group["keeper"]["draft_id"] == str(keeper.pk)
    assert {row["draft_id"] for row in group["archive"]} == {str(row.pk) for row in others}
    assert group["keeper"]["score"] == 0
    assert plan["unresolved_count"] == 0
    assert list(ListingDraft.objects.order_by("pk").values()) == before
    assert AuditLog.objects.count() == 0


def test_completeness_then_updated_at_then_highest_pk_choose_keeper(item):
    low = draft(item, title="Only title")
    older = draft(item, title="Title", price=Decimal("10"), id=UUID(int=1))
    newer = draft(item, title="Title", price=Decimal("10"), id=UUID(int=2))
    now = timezone.now()
    ListingDraft.objects.filter(pk=older.pk).update(updated_at=now - timedelta(days=1))
    ListingDraft.objects.filter(pk=newer.pk).update(updated_at=now)
    assert migration_a_plan()["groups"][0]["keeper"]["draft_id"] == str(newer.pk)
    ListingDraft.objects.filter(pk=older.pk).update(updated_at=now)
    assert migration_a_plan()["groups"][0]["keeper"]["draft_id"] == str(newer.pk)
    assert low.pk != newer.pk


@pytest.mark.parametrize("offer_status", ["staged", "ready", "publish_failed"])
def test_multiple_offer_holders_leave_whole_group_unresolved(item, offer_status):
    first = draft(item, status=offer_status, channel_data={"offer_id": "offer-one"})
    second = draft(item, channel_data={"offer_id": "offer-two"})
    draft(item)
    plan = migration_a_plan()
    assert plan["archive_count"] == 0
    assert plan["unresolved_count"] == 1
    assert plan["groups"][0]["keeper"] is None
    assert plan["groups"][0]["unresolved"] == ["multiple_staged_offers"]
    assert {r["draft_id"] for r in plan["groups"][0]["active"]} >= {str(first.pk), str(second.pk)}


@pytest.mark.parametrize("state", ["publishing", "publish_unknown"])
def test_uncertain_publish_outcome_is_active_but_never_auto_archived(item, state):
    row = draft(item, status=state)
    draft(item, title="More complete")
    plan = migration_a_plan()
    assert plan["archive_count"] == 0
    assert "publish_outcome_requires_reconciliation" in plan["groups"][0]["unresolved"]
    assert ListingDraft.objects.filter(active_draft_filter(), pk=row.pk).exists()


def test_grouping_is_per_item_and_channel_and_published_or_archived_do_not_compete(item):
    published = draft(item, status="published", title="Full old history", channel_data={"offer_id": "old-offer", "listing_id": "old-listing"})
    draft(item, status="archived")
    wanted = draft(item, title="One")
    other_channel = draft(item, channel="generic", title="Other channel")
    plan = migration_a_plan()
    groups = {group["channel"]: group for group in plan["groups"]}
    assert groups["ebay_au"]["keeper"]["draft_id"] == str(wanted.pk)
    assert str(published.pk) in groups["ebay_au"]["preserved_terminal"]
    assert groups["generic"]["keeper"]["draft_id"] == str(other_channel.pk)
    assert plan["archive_count"] == 0


@pytest.mark.parametrize("proof", ["listing_id", "channel_listing"])
def test_inconsistent_active_status_with_published_proof_is_preserved_unresolved(item, proof):
    row = draft(item, status="ready", channel_data={"listing_id": "already-live"} if proof == "listing_id" else {})
    if proof == "channel_listing":
        ChannelListing.objects.create(item=item, source_listing_draft=row, channel="ebay")
    draft(item)
    plan = migration_a_plan()
    assert plan["archive_count"] == 0
    assert "active_status_with_published_history" in plan["groups"][0]["unresolved"]
    assert row.is_read_only


def test_migration_command_defaults_to_read_only_and_requires_exact_approval(item):
    draft(item, title="Keep")
    draft(item)
    before = list(ListingDraft.objects.order_by("pk").values())
    for options in ({}, {"dry_run": True}):
        out = StringIO()
        call_command("canonicalize_listing_drafts", stdout=out, **options)
        report = json.loads(out.getvalue())
        assert report["mode"] == "dry_run"
        assert report["archive_count"] == 1
    assert list(ListingDraft.objects.order_by("pk").values()) == before
    assert AuditLog.objects.count() == 0
    with pytest.raises(CommandError):
        call_command("canonicalize_listing_drafts", apply=True, stdout=StringIO())
    with pytest.raises(CommandError):
        call_command("canonicalize_listing_drafts", apply=True, approved_fingerprint="wrong", stdout=StringIO())
    assert list(ListingDraft.objects.order_by("pk").values()) == before


def test_apply_archives_exactly_planned_rows_audits_each_and_is_idempotent(item):
    keeper = draft(item, title="Keep", channel_data={"offer_id": "offer-one"})
    victims = [draft(item, status=status) for status in ["draft", "exported", "publish_failed"]]
    published = draft(item, status="published", channel_data={"listing_id": "history"})
    listing = ChannelListing.objects.create(item=item, source_listing_draft=published, channel="ebay")
    history = AuditLog.objects.create(action="ebay.publish.succeeded", target_id=str(published.pk), payload={"listing_id": "history"})
    protected = (ListingDraft.objects.filter(pk=published.pk).values().get(), ChannelListing.objects.values().get(pk=listing.pk), AuditLog.objects.values().get(pk=history.pk))
    plan = migration_a_plan()
    apply_migration_a(plan["fingerprint"])
    keeper.refresh_from_db()
    assert keeper.status == "draft"
    assert ListingDraft.objects.filter(pk__in=[row.pk for row in victims], status="archived").count() == 3
    logs = list(AuditLog.objects.filter(action="listing.draft.archived"))
    assert len(logs) == 3
    assert {row.payload["pre_archive_status"] for row in logs} == {"draft", "exported", "publish_failed"}
    assert all(row.payload["keeper_id"] == str(keeper.pk) and row.payload["offer_id"] is None and row.payload["score"] == 0 for row in logs)
    assert protected == (ListingDraft.objects.filter(pk=published.pk).values().get(), ChannelListing.objects.values().get(pk=listing.pk), AuditLog.objects.values().get(pk=history.pk))
    apply_migration_a(migration_a_plan()["fingerprint"])
    assert AuditLog.objects.filter(action="listing.draft.archived").count() == 3


def test_stale_approval_and_audit_failure_roll_back_every_archive(item, monkeypatch):
    draft(item, title="Keep")
    victim = draft(item)
    plan = migration_a_plan()
    victim.title = "Changed"
    victim.save()
    with pytest.raises(ValidationError):
        apply_migration_a(plan["fingerprint"])
    before = list(ListingDraft.objects.order_by("pk").values())
    def fail(**kwargs):
        raise RuntimeError("Synthetic audit failure")
    monkeypatch.setattr("apps.listing.canonical.record", fail)
    with pytest.raises(RuntimeError):
        apply_migration_a(migration_a_plan()["fingerprint"])
    assert list(ListingDraft.objects.order_by("pk").values()) == before
    assert AuditLog.objects.count() == 0


@pytest.mark.parametrize("status", ["published", "archived"])
def test_historical_drafts_are_immutable_through_model_bulk_cascade_and_api(item, api_client, status):
    row = draft(item, status=status, title="Retained history")
    before = ListingDraft.objects.values().get(pk=row.pk)
    for write in [
        lambda: row.save(), lambda: row.delete(), lambda: ListingDraft.objects.filter(pk=row.pk).delete(),
        lambda: ListingDraft.objects.filter(pk=row.pk).update(title="Bad"),
        lambda: ListingDraft.objects.bulk_update([row], ["title"]), lambda: item.delete(),
    ]:
        with pytest.raises(ValidationError):
            with transaction.atomic():
                write()
    assert api_client.patch(f"/api/listing-drafts/{row.pk}/", {"title": "Bad"}, format="json").status_code == 400
    assert api_client.delete(f"/api/listing-drafts/{row.pk}/").status_code == 400
    for action in ["generate", "stage", "withdraw", "publish"]:
        assert api_client.post(f"/api/listing-drafts/{row.pk}/{action}/", {"fields": ["title"]}, format="json").status_code == 400
    assert api_client.get(f"/api/listing-drafts/{row.pk}/").status_code == 200
    assert api_client.get(f"/api/listing-drafts/{row.pk}/export/").status_code == 200
    assert ListingDraft.objects.values().get(pk=row.pk) == before
    assert AuditLog.objects.count() == 0


def test_canonical_create_reuses_staged_keeper_without_writes_and_lists_it_first(item, api_client):
    keeper = draft(item, status="staged", channel_data={"offer_id": "356038014011"})
    draft(item, title="Newer incomplete")
    before = list(ListingDraft.objects.order_by("pk").values())
    response = api_client.post(f"/api/items/{item.pk}/listing-drafts/", {}, format="json")
    assert response.status_code == 200, response.data
    assert response.data["id"] == str(keeper.pk)
    rows = api_client.get(f"/api/items/{item.pk}/listing-drafts/").data["results"]
    assert rows[0]["id"] == str(keeper.pk)
    assert list(ListingDraft.objects.order_by("pk").values()) == before
    assert api_client.post("/api/listing-drafts/", {"item": str(item.pk)}, format="json").status_code == 400


def test_create_is_per_channel_and_unresolved_groups_refuse_creation(item, api_client):
    draft(item, channel="generic")
    response = api_client.post(f"/api/items/{item.pk}/listing-drafts/", {}, format="json")
    assert response.status_code == 201, response.data
    assert response.data["channel"] == "ebay_au"
    current = ListingDraft.objects.get(pk=response.data["id"])
    current.channel_data = {"offer_id": "first"}
    current.save()
    draft(item, channel_data={"offer_id": "second"})
    before = ListingDraft.objects.count()
    assert api_client.post(f"/api/items/{item.pk}/listing-drafts/", {}, format="json").status_code == 400
    assert ListingDraft.objects.count() == before


def test_relisting_copies_published_content_without_remote_state_or_history_mutation(item, api_client):
    published = draft(item, status="published", title="Human title", description_html="<p>Human description</p>", price=Decimal("360"), photo_ids=[str(UUID(int=123))], channel_data={"listing_id": "live", "offer_id": "old", "eps_image_urls": ["old"], "category_id": "139965", "payment_policy_id": "p1", "listing_duration": "GTC", "unexpected_private_field": "never-copy"})
    before = ListingDraft.objects.values().get(pk=published.pk)
    response = api_client.post(f"/api/items/{item.pk}/listing-drafts/", {}, format="json")
    assert response.status_code == 201, response.data
    row = ListingDraft.objects.get(pk=response.data["id"])
    assert row.pk != published.pk and row.status == "draft"
    assert row.title == published.title and row.price == published.price and row.photo_ids == published.photo_ids
    assert row.channel_data == {"category_id": "139965", "payment_policy_id": "p1", "listing_duration": "GTC"}
    assert row.generated_meta["relisted_from"] == str(published.pk)
    assert ListingDraft.objects.values().get(pk=published.pk) == before
    assert AuditLog.objects.count() == 0


def test_local_planning_apply_and_resolution_never_call_external_adapters(item, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("No network or eBay adapter may be used")
    import integrations.ebay as ebay
    for name in ["get_ebay_auth_adapter", "get_ebay_taxonomy_adapter", "get_ebay_inventory_adapter", "get_ebay_media_adapter"]:
        monkeypatch.setattr(ebay, name, forbidden)
    keeper = draft(item, title="Keep", channel_data={"offer_id": "one", "api_key": "not-for-audit"})
    draft(item)
    plan = migration_a_plan()
    assert "not-for-audit" not in json.dumps(plan)
    apply_migration_a(plan["fingerprint"])
    assert "not-for-audit" not in json.dumps(list(AuditLog.objects.values_list("payload", flat=True)))
    resolved, created = get_or_create_canonical_draft(item, create_new=forbidden)
    assert resolved.pk == keeper.pk and created is False
    keeper.status = "archived"
    keeper.save()
    with pytest.raises(ValidationError):
        stage_draft(keeper)
    with pytest.raises(ValidationError):
        withdraw_staged(keeper)
