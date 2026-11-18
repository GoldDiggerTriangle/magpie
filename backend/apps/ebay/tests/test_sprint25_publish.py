from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import timedelta
from importlib import import_module
from threading import Barrier, Event
from types import SimpleNamespace
import uuid

import pytest
from django.apps import apps
from django.core.exceptions import ValidationError
from django.db import connections, DatabaseError, IntegrityError, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

import integrations.ebay as ebay
from apps.audit.models import AuditLog
from apps.catalog.models import ProductCategory
from apps.ebay import publish_state as state
from apps.ebay.review import prepare_review, live_validation, normalized_fees
from apps.ebay.staging import stage_draft, withdraw_staged
from apps.ebay.staging import _inventory_item_payload
from apps.ebay.conditions import CONDITION_ENUMS
from apps.ebay.workflow_errors import WorkflowError
from apps.inventory.models import InventoryItem
from apps.listing.models import ChannelListing, ListingDraft
from apps.listing.serializers import ListingDraftSerializer
from apps.photos.models import PhotoAsset
from apps.ebay.tests.test_sprint7 import ebay_settings, credential, merchant_location, item, category, add_photo, make_draft


pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def draft(item, credential, merchant_location):
    add_photo(item)
    row = make_draft(item)
    row.refresh_from_db()
    return row


def stage(draft):
    return stage_draft(draft, review_id=prepare_review(draft).pk)


def publish(draft, *, mode="full", **kwargs):
    review = prepare_review(draft, mode=mode)
    return state.publish_draft(draft, review_id=review.pk, mode=mode, confirm_sku=draft.item.sku if mode == "full" else "", **kwargs)


def test_review_and_stage_are_explicit_and_review_is_immutable(draft):
    old = draft.updated_at
    with pytest.raises(WorkflowError, match="review"):
        stage_draft(draft)
    review = prepare_review(draft)
    draft.refresh_from_db()
    assert draft.updated_at == old and not draft.channel_data.get("offer_id")
    with pytest.raises(ValidationError, match="immutable"):
        review.save()
    staged = stage_draft(draft, review_id=review.pk)
    assert staged.staging_state == "verified" and staged.staged_fingerprint
    assert len(staged.channel_data["eps_photos"]) == 1
    preview = prepare_review(staged).snapshot
    assert preview["can_publish"], preview["checks"] + preview["publish_checks"]
    assert ebay.FakeEbayInventoryAdapter.publish_count == 0


@pytest.mark.parametrize("field,value,blocker", [
    ("title", "", "title_missing"), ("price", None, "price_invalid"),
    ("photo_ids", [], "photos"), ("quantity", 2, "available_stock"),
    ("category_id", "", "category_id"), ("condition_id", "", "ebay_condition"),
    ("fulfillment_policy_id", "missing", "fulfillment_policy"),
    ("payment_policy_id", "missing", "payment_policy"), ("return_policy_id", "missing", "return_policy"),
    ("merchant_location_key", "", "merchant_location"), ("listing_duration", "DAYS_7", "listing_duration"),
    ("item_specifics", [], "aspect:Brand"), ("listing_format", "", "listing_format"),
])
def test_each_readiness_gate_names_blocker(draft, field, value, blocker):
    if hasattr(draft, field):
        setattr(draft, field, value)
    else:
        draft.channel_data[field] = value
    result = live_validation(draft)
    assert blocker in {r["key"] for r in result["checks"]}
    assert all(r["field"] and r["message"] for r in result["checks"])


def test_price_source_and_recommended_aspects_conditionless(draft, monkeypatch):
    draft.generated_meta = {}
    assert "price_source" in {r["key"] for r in live_validation(draft)["checks"]}
    draft.generated_meta = {"price_source": {"kind": "human_asking", "value": "1.00", "currency": "AUD"}}
    draft.channel_data["condition_id"] = ""
    monkeypatch.setattr(ebay.FakeEbayTaxonomyAdapter, "item_condition_policy", lambda self, **kw: {"required": False, "conditions": [], **kw})
    assert not live_validation(draft)["checks"]


@pytest.mark.parametrize("condition_id,enum", list(CONDITION_ENUMS.items()))
def test_selected_ebay_condition_is_never_replaced_by_global_item_condition(draft, condition_id, enum):
    draft.channel_data["condition_id"] = condition_id
    assert _inventory_item_payload(draft, ["fake-eps://owned.jpg"])["condition"] == enum


def test_conditionless_category_omits_obsolete_local_selection(draft):
    policy = {"category_id": draft.channel_data["category_id"], "marketplace": "EBAY_AU", "fetched_at": timezone.now().isoformat(), "required": False, "conditions": []}
    assert "condition" not in _inventory_item_payload(draft, ["fake-eps://own"], condition_policy=policy)
    draft.channel_data["condition_id"] = "unknown"
    with pytest.raises(ValidationError, match="verified"):
        _inventory_item_payload(draft, ["fake-eps://own"])


def test_atomic_claim_sql_records_prior_status_and_all_review_identity_checks(draft):
    from django.db import connection
    draft = stage(draft)
    review = prepare_review(draft)
    with CaptureQueriesContext(connection) as captured:
        state.claim(draft, review)
    updates = [row["sql"] for row in captured if row["sql"].lstrip().upper().startswith("UPDATE")]
    assert len(updates) == 1
    sql = updates[0]
    assert '"publish_prior_status" = "listing_listingdraft"."status"' in sql
    for column in ["updated_at", "staged_fingerprint", "offer_id", "listing_id", "publish_attempt", "publish_started_at"]:
        assert column in sql


def test_required_selection_only_aspect_is_validated_without_optional_blockers(draft, monkeypatch):
    original = ebay.FakeEbayTaxonomyAdapter.item_aspects
    def aspects(self, **kw):
        return [*original(self, **kw), {"name": "Country of Origin", "required": True, "mode": "SELECTION_ONLY", "values": ["Australia", "Canada"]}, {"name": "Optional", "required": False, "mode": "SELECTION_ONLY", "values": ["A"]}]
    monkeypatch.setattr(ebay.FakeEbayTaxonomyAdapter, "item_aspects", aspects)
    draft.item_specifics.append({"name": "Country of Origin", "value": "Maryborough"})
    assert "aspect_value:Country of Origin" in {r["key"] for r in live_validation(draft)["checks"]}
    draft.item_specifics[-1]["value"] = "Australia"
    assert not live_validation(draft)["checks"]


def test_startup_and_command_recover_stale_rows_without_any_provider_call(draft, monkeypatch):
    from django.core.management import call_command
    from apps.ebay.startup import recover_interrupted_publishes
    draft = stage(draft)
    state.claim(draft, prepare_review(draft))
    ListingDraft.objects.filter(pk=draft.pk).update(publish_started_at=timezone.now()-timedelta(minutes=11))
    monkeypatch.setattr(ebay, "get_ebay_inventory_adapter", lambda: pytest.fail("Recovery must be local"))
    recover_interrupted_publishes()
    draft.refresh_from_db()
    assert draft.status == "publish_unknown"
    from io import StringIO
    out = StringIO()
    call_command("recover_ebay_publishes", stdout=out)
    assert "0" in out.getvalue()


def test_startup_never_rewrites_historic_listing_ids(draft):
    ListingDraft.objects.filter(pk=draft.pk).update(status="publishing", publish_started_at=timezone.now()-timedelta(minutes=11), channel_data={"listing_id": "historic-live"})
    before = ListingDraft.objects.values().get(pk=draft.pk)
    assert state.recover_stale() == 0
    assert ListingDraft.objects.values().get(pk=draft.pk) == before


@pytest.mark.parametrize("mode", ["full", "quick"])
def test_changed_draft_or_terms_require_new_review(draft, monkeypatch, mode):
    draft = stage(draft)
    review = prepare_review(draft, mode=mode)
    original = ebay.FakeEbayAccountAdapter.list_policies
    def changed(self, **kw):
        rows = deepcopy(original(self, **kw))
        rows[0]["newTerm"] = "changed after review"
        return rows
    monkeypatch.setattr(ebay.FakeEbayAccountAdapter, "list_policies", changed)
    with pytest.raises(WorkflowError, match="changed"):
        state.publish_draft(draft, review_id=review.pk, mode=mode, confirm_sku=draft.item.sku)
    assert ebay.FakeEbayInventoryAdapter.publish_count == 0


@pytest.mark.parametrize("mode", ["full", "quick"])
def test_local_drift_cannot_silently_restage(draft, mode):
    draft = stage(draft)
    draft.title = "Different human title"
    draft.save()
    review = prepare_review(draft, mode=mode)
    assert "staged_drift" in {r["key"] for r in review.snapshot["publish_checks"]}
    with pytest.raises(WorkflowError):
        state.publish_draft(draft, review_id=review.pk, confirm_sku=draft.item.sku, mode=mode)
    assert ebay.FakeEbayInventoryAdapter.update_count == 0
    assert ebay.FakeEbayInventoryAdapter.publish_count == 0
    if mode == "full":
        draft = stage(draft)
        assert prepare_review(draft).snapshot["can_publish"]


def test_photo_expiry_between_review_and_publish_needs_explicit_update(draft):
    draft = stage(draft)
    review = prepare_review(draft)
    data = deepcopy(draft.channel_data)
    data["eps_photos"][0]["uploaded_at"] = (timezone.now()-timedelta(days=31)).isoformat()
    # Simulate time-only expiry without editing any listing value/revision.
    ListingDraft.objects.filter(pk=draft.pk).update(channel_data=data)
    with pytest.raises(WorkflowError):
        state.publish_draft(draft, review_id=review.pk, confirm_sku=draft.item.sku)
    assert ebay.FakeEbayMediaAdapter.upload_count == 1
    assert ebay.FakeEbayInventoryAdapter.publish_count == 0
    stage(draft)
    assert ebay.FakeEbayMediaAdapter.upload_count == 2


def test_partial_update_is_unverified(draft, monkeypatch):
    draft = stage(draft)
    def fail(*a, **kw):
        raise TimeoutError("not surfaced")
    monkeypatch.setattr(ebay.FakeEbayInventoryAdapter, "update_offer", fail)
    with pytest.raises(WorkflowError):
        stage(draft)
    draft.refresh_from_db()
    assert draft.staging_state == "unverified" and not draft.staged_fingerprint
    assert not prepare_review(draft).snapshot["can_publish"]


@pytest.mark.parametrize("created", [False, True])
def test_create_timeout_reconciles_before_any_new_create(draft, monkeypatch, created):
    original = ebay.FakeEbayInventoryAdapter.create_offer
    def interrupted(self, **kw):
        if created:
            original(self, **kw)
        raise TimeoutError("not surfaced")
    monkeypatch.setattr(ebay.FakeEbayInventoryAdapter, "create_offer", interrupted)
    with pytest.raises(WorkflowError):
        stage(draft)
    draft.refresh_from_db()
    assert draft.staging_state == "create_unknown"
    monkeypatch.setattr(ebay.FakeEbayInventoryAdapter, "create_offer", original)
    if created:
        recovered = stage(draft)
        assert recovered.channel_data["offer_id"] == "fake-offer-1"
        assert ebay.FakeEbayInventoryAdapter.create_count == 1
    else:
        with pytest.raises(WorkflowError, match="unresolved"):
            stage(draft)
        assert ebay.FakeEbayInventoryAdapter.create_count == 0


def test_success_atomic_actual_publish_and_history_guards(draft):
    draft = stage(draft)
    result = publish(draft, mode="quick")
    assert result.status == "published"
    assert ChannelListing.objects.get(source_listing_draft=result).external_listing_id == result.channel_data["listing_id"]
    assert InventoryItem.objects.get(pk=draft.item_id).status == "listed"
    assert AuditLog.objects.filter(action="ebay.publish.succeeded").count() == 1
    assert ebay.FakeEbayInventoryAdapter.publish_count == 1
    with pytest.raises(WorkflowError):
        state.publish_draft(result)
    with pytest.raises(ValidationError):
        result.save()


def test_definite_failure_restores_claimed_prior_status_and_safe_error(draft):
    draft = stage(draft)
    ListingDraft.objects.filter(pk=draft.pk).update(status="ready")
    draft.refresh_from_db()
    ebay.FakeEbayInventoryAdapter.publish_should_fail = True
    with pytest.raises(WorkflowError):
        publish(draft)
    draft.refresh_from_db()
    assert draft.publish_prior_status == draft.status == "ready"
    assert draft.publish_error["http_status"] == 400
    assert draft.publish_error["error_ids"] == [25002]


def test_publish_success_db_failure_then_reconcile_no_second_send(draft, monkeypatch):
    draft = stage(draft)
    original = state.record_success
    monkeypatch.setattr(state, "record_success", lambda *a, **kw: (_ for _ in ()).throw(DatabaseError()))
    with pytest.raises(WorkflowError):
        publish(draft)
    draft.refresh_from_db()
    assert draft.status == "publish_unknown" and not ChannelListing.objects.exists()
    monkeypatch.setattr(state, "record_success", original)
    recovered = state.reconcile_draft(draft)
    assert recovered.status == "published" and ChannelListing.objects.count() == 1
    state.reconcile_draft(recovered)
    assert ebay.FakeEbayInventoryAdapter.publish_count == 1


def test_success_transaction_rolls_back_all_local_writes_on_audit_failure(draft, monkeypatch):
    draft = stage(draft)
    original = state.record
    def fail_audit(**kw):
        if kw["action"] == "ebay.publish.succeeded":
            raise DatabaseError("simulated audit commit failure")
        return original(**kw)
    monkeypatch.setattr(state, "record", fail_audit)
    with pytest.raises(WorkflowError):
        publish(draft)
    draft.refresh_from_db()
    assert draft.status == "publish_unknown" and not draft.channel_data.get("listing_id")
    assert not ChannelListing.objects.exists()
    assert InventoryItem.objects.get(pk=draft.item_id).status == "ready_to_list"
    assert not AuditLog.objects.filter(action="ebay.publish.succeeded").exists()
    monkeypatch.setattr(state, "record", original)
    assert state.reconcile_draft(draft).status == "published"
    assert ebay.FakeEbayInventoryAdapter.publish_count == 1


def test_hard_deadline_is_not_cancellation_and_does_not_allow_retry(concurrent_draft, monkeypatch):
    # This is a real two-connection test: use the file-backed SQLite/PG fixture,
    # not SQLite's shared-memory tables, whose transient read locks bypass busy_timeout.
    draft = concurrent_draft
    entered, release = Event(), Event()
    original = ebay.FakeEbayInventoryAdapter.publish_offer
    def delayed(self, **kw):
        entered.set()
        assert release.wait(10)
        return original(self, **kw)
    assert state.PUBLISH_TIMEOUT_SECONDS == 60
    monkeypatch.setattr(state, "PUBLISH_TIMEOUT_SECONDS", 0.1)
    monkeypatch.setattr(ebay.FakeEbayInventoryAdapter, "publish_offer", delayed)
    class TransportDeadlineExecutor(ThreadPoolExecutor):
        def submit(self, fn, *args, **kwargs):
            future = super().submit(fn, *args, **kwargs)
            result = future.result
            def after_transport_started(timeout=None):
                # Coordinate the simulated transport timeout with the event;
                # local preflight work must not race the artificial 100ms clock.
                assert entered.wait(10)
                return result(timeout=timeout)
            future.result = after_transport_started
            return future
    monkeypatch.setattr(state, "ThreadPoolExecutor", TransportDeadlineExecutor)
    try:
        with pytest.raises(WorkflowError, match="unknown"):
            publish(draft)
        assert entered.is_set()
        draft.refresh_from_db()
        assert draft.status == "publish_unknown" and draft.publish_call_started_at
        with pytest.raises(WorkflowError):
            state.publish_draft(draft)
        assert state.reconcile_draft(draft).status == "publish_unknown"
    finally:
        release.set()
        # Wait for the one original worker, never launch another publish.
        import time
        for _ in range(100):
            draft.refresh_from_db()
            if draft.status == "published":
                break
            time.sleep(0.02)
    assert draft.status == "published" and ebay.FakeEbayInventoryAdapter.publish_count == 1


def test_api_confirmation_and_server_owned_state_cannot_be_forged(draft, django_user_model):
    user = django_user_model.objects.create_user(username="review-user")
    client = APIClient()
    client.force_authenticate(user)
    base = f"/api/listing-drafts/{draft.pk}/"
    for payload in [{"status": "published"}, {"status": "publish_unknown"}, {"channel_data": {"offer_id": "forged"}}, {"channel_data": {"listing_id": "forged"}}]:
        assert client.patch(base, payload, format="json").status_code == 400
    assert client.post(base+"stage/", {}, format="json").status_code == 409
    assert client.post(base+"withdraw/", {}, format="json").status_code == 400
    assert client.post(base+"preview/", {}, format="json").status_code == 200
    draft = stage(draft)
    state.claim(draft, prepare_review(draft))
    assert client.post(base+"archive/", {}, format="json").status_code == 400
    assert client.patch(base, {"title": "cannot edit in flight"}, format="json").status_code == 400
    health = client.get("/api/listing-drafts/publish-health/")
    assert health.status_code == 200 and health.data["drafts"][0]["sku"] == draft.item.sku


def test_identity_migration_precheck_and_constraints(draft):
    check = import_module("apps.listing.migrations.0007_reviewed_publish_protocol").identity_plan
    listing = ChannelListing.objects.create(item=draft.item, channel="ebay", external_listing_id="owned-listing")
    assert check(apps, "default") == [(listing.pk, "owned-listing")]
    with pytest.raises(IntegrityError), transaction.atomic():
        ChannelListing.objects.create(item=draft.item, channel="ebay", external_listing_id="owned-listing")
    listing.url = "https://www.ebay.com.au/itm/12345"
    listing.save()
    with pytest.raises(RuntimeError, match=draft.item.sku):
        check(apps, "default")


def test_no_network_or_raw_provider_payload_in_fake_publish(draft, monkeypatch):
    import socket
    monkeypatch.setattr(socket.socket, "connect", lambda *a, **kw: pytest.fail("Network forbidden in fake workflow"))
    draft = stage(draft)
    def rejected(*a, **kw):
        raise ebay.EbayHttpError("DO_NOT_SURFACE_PROVIDER_BODY", http_status=403, error_ids=(21919,))
    monkeypatch.setattr(ebay.FakeEbayInventoryAdapter, "publish_offer", rejected)
    with pytest.raises(WorkflowError) as error:
        publish(draft)
    assert "permission" in str(error.value) and "DO_NOT_SURFACE" not in str(error.value)
    draft.refresh_from_db()
    assert draft.publish_error["http_status"] == 403
    assert "DO_NOT_SURFACE" not in str(draft.publish_error)
    assert "DO_NOT_SURFACE" not in str(list(AuditLog.objects.values_list("payload", flat=True)))


@pytest.mark.parametrize("remote", ["published", "unpublished_unsent", "unpublished_sent", "missing", "unreachable"])
def test_stale_crash_reconcile_is_conservative(draft, monkeypatch, remote):
    draft = stage(draft)
    review = prepare_review(draft)
    attempt = state.claim(draft, review)
    ListingDraft.objects.filter(pk=draft.pk).update(publish_started_at=timezone.now()-timedelta(minutes=11), publish_call_started_at=None if remote == "unpublished_unsent" else timezone.now())
    assert state.recover_stale() == 1
    if remote == "published":
        ebay.FakeEbayInventoryAdapter.offers[review.offer_id].update(status="PUBLISHED", listingId="remote-listing")
    elif remote == "missing":
        del ebay.FakeEbayInventoryAdapter.offers[review.offer_id]
    elif remote == "unreachable":
        monkeypatch.setattr(ebay.FakeEbayInventoryAdapter, "get_offer", lambda *a, **kw: (_ for _ in ()).throw(TimeoutError()))
    result = state.reconcile_draft(draft)
    assert result.status == {"published": "published", "unpublished_unsent": "staged"}.get(remote, "publish_unknown")
    assert result.publish_attempt == attempt and ebay.FakeEbayInventoryAdapter.publish_count == 0


def test_no_edit_archive_stage_or_claim_during_unknown(draft):
    draft = stage(draft)
    review = prepare_review(draft)
    attempt = state.claim(draft, review)
    state.mark_unknown(draft.pk, attempt, {"kind": "timeout"})
    draft.refresh_from_db()
    for action in [lambda: draft.save(), lambda: stage_draft(draft, review_id=review.pk), lambda: prepare_review(draft), lambda: state.claim(draft, review)]:
        with pytest.raises((ValidationError, WorkflowError)):
            action()
    serializer = ListingDraftSerializer(draft, data={"title": "no edit"}, partial=True)
    assert not serializer.is_valid()


def test_late_attempt_cannot_overwrite_newer_attempt(draft):
    draft = stage(draft)
    old = state.claim(draft, prepare_review(draft))
    state.finish_failure(draft.pk, old, {"kind": "definite_failure"})
    draft.refresh_from_db()
    new = state.claim(draft, prepare_review(draft))
    assert new != old
    assert not state.record_success(draft.pk, old, "late-listing")
    assert not state.finish_failure(draft.pk, old, {})
    assert not state.mark_unknown(draft.pk, old, {})
    draft.refresh_from_db()
    assert draft.status == "publishing" and draft.publish_attempt == new


def test_remove_refuses_published_and_requires_confirmed_absence(draft, monkeypatch):
    draft = stage(draft)
    offer = ebay.FakeEbayInventoryAdapter.offers[draft.channel_data["offer_id"]]
    offer.update(status="PUBLISHED", listingId="external-live")
    with pytest.raises(WorkflowError, match="separate"):
        withdraw_staged(draft)
    assert ebay.FakeEbayInventoryAdapter.withdraw_count == 0
    offer.pop("listingId")
    offer["status"] = "UNPUBLISHED"
    monkeypatch.setattr(ebay.FakeEbayInventoryAdapter, "delete_offer", lambda *a, **kw: None)
    with pytest.raises(WorkflowError, match="not confirmed"):
        withdraw_staged(draft)
    draft.refresh_from_db()
    assert draft.channel_data["offer_id"]


def test_fees_use_official_fee_summaries_schema():
    assert normalized_fees({"feeSummaries": [{"marketplaceId": "EBAY_AU", "fees": [{"feeType": "InsertionFee", "amount": {"value": "0.06", "currency": "AUD"}}]}]}, "offer") == [{"type": "InsertionFee", "value": "0.06", "currency": "AUD"}]


def test_real_publish_adapter_caps_socket_timeout_without_sending(monkeypatch):
    from apps.ebay import adapters
    calls = []
    def fake_request(*a, **kw):
        calls.append(kw)
        return {"listingId": "mocked-listing"}
    monkeypatch.setattr(adapters, "_request_json", fake_request)
    adapter = adapters.HttpEbayInventoryAdapter(environment="sandbox", timeout_seconds=600)
    assert adapter.publish_offer(access_token="fake-access", offer_id="fake-offer") == "mocked-listing"
    assert calls[0]["timeout_seconds"] == 60 and calls[0]["method"] == "POST"


@pytest.fixture
def concurrent_draft(tmp_path, django_db_blocker, monkeypatch, settings):
    """Real file-backed SQLite on its lane; real PostgreSQL on its lane."""
    settings.MEDIA_ROOT = tmp_path / "media"
    alias = "default"
    if connections[alias].vendor == "sqlite":
        alias = "publish_file"
        config = deepcopy(connections["default"].settings_dict)
        config.update(NAME=str(tmp_path / "publish.sqlite3"), OPTIONS={"timeout": 10})
        connections.databases[alias] = config
        with django_db_blocker.unblock():
            executor = MigrationExecutor(connections[alias])
            executor.migrate(executor.loader.graph.leaf_nodes())
    with django_db_blocker.unblock():
        monkeypatch.setattr("apps.ebay.review.get_access_token", lambda **kw: "fake-access")
        monkeypatch.setattr("apps.ebay.review.get_app_access_token", lambda **kw: "fake-app")
        monkeypatch.setattr("apps.ebay.publish_state.get_access_token", lambda **kw: "fake-access")
        monkeypatch.setattr("apps.ebay.staging.get_access_token", lambda **kw: "fake-access")
        ebay.FakeEbayInventoryAdapter.locations["first-flight-location"] = {"merchantLocationStatus": "ENABLED"}
        cat = ProductCategory.objects.using(alias).create(name="Race", slug="race", sku_prefix="RC")
        owned = InventoryItem.objects.using(alias).create(title="Owned race item", category=cat, sku="RC-00001", quantity_total=1)
        path = settings.MEDIA_ROOT / "race.jpg"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"owned-race-image")
        photo = PhotoAsset.objects.using(alias).create(item=owned, processed_path="race.jpg", original_path="race.jpg")
        # Reuse only the field data, not a default-database row or credential.
        draft = ListingDraft.objects.using(alias).create(item=owned, title="Race listing", description_html="<p>Own item</p>", listing_format="fixed", price="1.00", photo_ids=[str(photo.pk)], item_specifics=[{"name": "Brand", "value": "A"}, {"name": "Country/Region of Manufacture", "value": "Australia"}], generated_meta={"price_source": {"kind": "human_asking", "value": "1.00", "currency": "AUD"}}, channel_data={"category_id": "105848", "category_name": "Stamps", "condition_id": "3000", "listing_duration": "GTC", "merchant_location_key": "first-flight-location", "payment_policy_id": "fake-payment-policy", "fulfillment_policy_id": "fake-fulfillment-policy", "return_policy_id": "fake-return-policy"})
        try:
            yield stage(draft)
        finally:
            if alias != "default":
                connections[alias].close()
                del connections[alias]
                del connections.databases[alias]


def parallel(jobs, using):
    def worker(job):
        try:
            return job()
        except (WorkflowError, ValidationError, DatabaseError) as exc:
            return type(exc).__name__
        finally:
            connections[using].close()
    with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
        return list(pool.map(worker, jobs))


def test_simultaneous_publish_exactly_one_remote_call_and_listing(concurrent_draft):
    draft = concurrent_draft
    using = draft._state.db
    review = prepare_review(draft)
    barrier = Barrier(2)
    def request():
        barrier.wait(timeout=10)
        return state.publish_draft(state.fresh_draft(draft.pk, using), review_id=review.pk, confirm_sku=draft.item.sku)
    parallel([request, request], using)
    assert ebay.FakeEbayInventoryAdapter.publish_count == 1
    assert ChannelListing.objects.using(using).filter(source_listing_draft=draft).count() == 1
    assert AuditLog.objects.using(using).filter(action="ebay.publish.succeeded").count() == 1


@pytest.mark.parametrize("other", ["edit", "archive"])
def test_publish_claim_serializes_with_edit_or_archive(concurrent_draft, other):
    draft = concurrent_draft
    using = draft._state.db
    review = prepare_review(draft)
    barrier = Barrier(2)
    def claim():
        barrier.wait(timeout=10)
        return state.claim(draft, review)
    def mutate():
        stale = state.fresh_draft(draft.pk, using)
        barrier.wait(timeout=10)
        if other == "edit":
            stale.title = "Human change"
            stale.save(using=using)
        else:
            return state.mutable_rows(using).filter(pk=draft.pk, updated_at=review.draft_revision).update(status="archived", updated_at=timezone.now())
    parallel([claim, mutate], using)
    current = state.fresh_draft(draft.pk, using)
    if current.status == "publishing":
        assert current.title == draft.title
    else:
        assert current.status == "archived" or current.title == "Human change"
        assert not current.publish_attempt
    assert ebay.FakeEbayInventoryAdapter.publish_count == 0


def test_concurrent_reconcile_one_transaction_and_listing(concurrent_draft):
    draft = concurrent_draft
    using = draft._state.db
    state.claim(draft, prepare_review(draft))
    ebay.FakeEbayInventoryAdapter.offers[draft.channel_data["offer_id"]].update(status="PUBLISHED", listingId="already-live")
    barrier = Barrier(2)
    def reconcile():
        barrier.wait(timeout=10)
        return state.reconcile_draft(draft)
    parallel([reconcile, reconcile], using)
    assert state.fresh_draft(draft.pk, using).status == "published"
    assert ChannelListing.objects.using(using).count() == 1
    assert AuditLog.objects.using(using).filter(action="ebay.publish.succeeded").count() == 1
    assert ebay.FakeEbayInventoryAdapter.publish_count == 0
