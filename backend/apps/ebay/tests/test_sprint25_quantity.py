from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest.mock import Mock
import json

import pytest
from django.core.exceptions import ValidationError
from django.db import connections, DatabaseError, IntegrityError, transaction
from django.utils import timezone
from rest_framework.test import APIClient

import integrations.ebay as ebay
from apps.ebay import quantity as q
from apps.ebay.diagnostics import diagnostic
from apps.ebay.models import EbayListingAllocation, EbayOrderDuplicateCandidate, EbayOrderStaging, EbayQuantityUpdate
from apps.ebay.review import prepare_review
from apps.ebay.workflow_errors import WorkflowError
from apps.inventory.models import InventoryItem
from apps.listing.models import ChannelListing, ListingDraft
from apps.sales.models import SaleRecord
from apps.sales.services import create_sale_record
from apps.ebay.tests.test_sprint7 import ebay_settings, credential, merchant_location, item, category
from apps.ebay.tests.test_sprint25_publish import draft, stage, publish, concurrent_draft

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def allocation(draft, monkeypatch):
    draft.item.quantity_total = 5
    draft.item.save()
    draft.quantity = 5
    draft.save()
    published = publish(stage(draft))
    allocation = EbayListingAllocation.objects.get(draft=published)
    check = q.check_quantity(allocation)
    allocation.refresh_from_db()
    assert check["inventory_available"] == check["offer_available"] == 5
    return allocation


def sale(item, quantity=1, **values):
    return create_sale_record(data={"item": item, "quantity": quantity, "sale_price": "10.00", "sale_date": timezone.localdate(), "channel": "manual", **values})


def payload(allocation, wanted=None):
    state = q.item_quantity_state(allocation.item, allocation.environment)
    return {**{k: state[k] for k in ("stock_revision", "stock_fingerprint", "allocation_revision")}, "quantity": wanted if wanted is not None else state["target"]}


def test_legacy_listing_has_no_backfill_warning_or_write(item):
    draft = ListingDraft.objects.create(item=item, status="published", quantity=1)
    ChannelListing.objects.create(item=item, channel="ebay", source_listing_draft=draft, external_listing_id="history")
    before = (draft.updated_at, draft.quantity, draft.channel_data)
    state = q.item_quantity_state(item, "sandbox")
    assert state["state"] == "allocation_not_recorded"
    assert not state["can_write"] and not state["urgent"] and "allocation_id" not in state
    assert not EbayListingAllocation.objects.exists()
    draft.refresh_from_db()
    assert before == (draft.updated_at, draft.quantity, draft.channel_data)


def test_local_sale_exact_reduction_and_immutable_history(allocation):
    original = ListingDraft.objects.values().get(pk=allocation.draft_id)
    sale(allocation.item, 2)
    state = q.item_quantity_state(allocation.item, "sandbox")
    assert state["target"] == 3 and state["urgent"] and state["can_write"]
    assert state["label"] == "Update eBay: 5 -> 3"
    result = q.update_quantity(allocation, payload(allocation))
    assert result["target"] == result["inventory_available"] == result["offer_available"] == 3
    assert not result["urgent"]
    assert original == ListingDraft.objects.values().get(pk=allocation.draft_id)
    assert EbayQuantityUpdate.objects.get().outcome == "verified"


def test_partial_allocation_never_replenishes_or_flags_lower_quantity(allocation):
    allocation.item.quantity_total = 10
    allocation.item.save()
    state = q.item_quantity_state(allocation.item, "sandbox")
    assert state["remaining"] == 10 and state["target"] == 5 and not state["urgent"]
    sale(allocation.item, 2)
    assert q.item_quantity_state(allocation.item, "sandbox")["target"] == 5
    assert not q.item_quantity_state(allocation.item, "sandbox")["urgent"]


def test_pending_duplicate_and_later_manual_match_count_once(allocation):
    manual = sale(allocation.item, 2)
    candidate = EbayOrderDuplicateCandidate.objects.create(environment="sandbox", ebay_order_id="o", ebay_line_item_id="l", sku=allocation.sku,
        item=allocation.item, manual_sale=manual, quantity=2, line_price="10.00", sale_date=timezone.localdate())
    staging = EbayOrderStaging.objects.create(environment="sandbox", ebay_order_id="o", ebay_line_item_id="l", sku=allocation.sku,
        quantity=2, line_price="10.00", sale_date=timezone.localdate())
    before = q.stock_basis(allocation.item, "sandbox")
    assert before["remaining"] == 3 and before["pending_units"] == 0
    from apps.ebay.order_sync import resolve_duplicate_candidate
    resolve_duplicate_candidate(candidate, action="link")
    after = q.stock_basis(allocation.item, "sandbox")
    assert after["remaining"] == 3 and len(after["events"]) == 1
    assert q.allocation_target(allocation, after) == 3
    assert staging.status == "pending"  # retrieval did not create a second sale


def test_pending_known_and_unlinked_orders_guard_increases(allocation):
    EbayOrderStaging.objects.create(environment="sandbox", ebay_order_id="pending", ebay_line_item_id="1", sku=allocation.sku,
        quantity=2, line_price="10.00", sale_date=timezone.localdate())
    assert q.stock_basis(allocation.item, "sandbox")["remaining"] == 3
    with pytest.raises(WorkflowError):
        q.update_quantity(allocation, payload(allocation, 4))
    EbayOrderStaging.objects.create(environment="sandbox", ebay_order_id="unlinked", ebay_line_item_id="1", sku="not-owned",
        quantity=1, line_price="10.00", sale_date=timezone.localdate())
    assert q.stock_basis(allocation.item, "sandbox")["unlinked_orders"] == 1
    assert q.update_quantity(allocation, payload(allocation, 3))["inventory_available"] == 3


def test_unlinked_order_blocks_restock_but_not_a_safe_reduction(allocation):
    allocation.item.quantity_total = 8
    allocation.item.save()
    EbayOrderStaging.objects.create(environment="sandbox", ebay_order_id="unlinked-restock", ebay_line_item_id="1", sku="not-owned",
        quantity=1, line_price="10.00", sale_date=timezone.localdate())
    with pytest.raises(WorkflowError, match="pending/unlinked"):
        q.update_quantity(allocation, payload(allocation, 6))
    assert q.update_quantity(allocation, payload(allocation, 3))["target"] == 3


def test_zero_stock_requires_explicit_takedown(allocation, monkeypatch):
    sale(allocation.item, 5)
    remote = Mock()
    monkeypatch.setattr(q.ebay, "get_ebay_inventory_adapter", remote)
    state = q.item_quantity_state(allocation.item, "sandbox")
    assert state["state"] == "take_down" and not state["can_write"]
    with pytest.raises(WorkflowError, match="take-down"):
        q.update_quantity(allocation, payload(allocation, 0))
    assert not remote.called and allocation.channel_listing.ended_at is None


def test_restock_is_only_explicit_human_increase(allocation):
    allocation.item.quantity_total = 8
    allocation.item.save()
    assert q.item_quantity_state(allocation.item, "sandbox")["target"] == 5
    result = q.update_quantity(allocation, payload(allocation, 7))
    assert result["inventory_available"] == 7 and result["target"] == 7


def test_old_quantity_review_refuses_changed_stock(allocation):
    old = payload(allocation, 4)
    sale(allocation.item, 1)
    with pytest.raises(WorkflowError, match="changed"):
        q.update_quantity(allocation, old)
    assert not EbayQuantityUpdate.objects.exists()


def test_timeout_then_ebay_sale_reconciles_without_retry(allocation, monkeypatch):
    original = ebay.FakeEbayInventoryAdapter.update_quantity
    calls = []
    def timeout(self, **kwargs):
        calls.append(kwargs["quantity"])
        original(self, **kwargs)
        raise TimeoutError("synthetic timeout")
    monkeypatch.setattr(ebay.FakeEbayInventoryAdapter, "update_quantity", timeout)
    result = q.update_quantity(allocation, payload(allocation, 4))
    assert result["state"] == "unknown" and not result["can_write"]
    with pytest.raises(WorkflowError):
        q.update_quantity(allocation, payload(allocation, 4))
    allocation.refresh_from_db()
    with pytest.raises(WorkflowError, match="timeout is not cancellation"):
        q.check_quantity(allocation)
    EbayQuantityUpdate.objects.update(request_sent_at=timezone.now() - timedelta(minutes=11))
    sale(allocation.item, 1, channel="ebay_au", ebay_order_id="after-timeout", ebay_line_item_id="one")
    ebay.FakeEbayInventoryAdapter.inventory_items[allocation.sku]["availability"]["shipToLocationAvailability"]["quantity"] = 3
    ebay.FakeEbayInventoryAdapter.offers[allocation.offer_id]["availableQuantity"] = 3
    allocation.refresh_from_db()
    result = q.check_quantity(allocation)
    assert not result["attempt_id"] and result["target"] == 3
    assert calls == [4]


def test_missing_or_mismatched_remote_observation_stays_unknown(allocation, monkeypatch):
    def partial(self, **kwargs):
        self.inventory_items[kwargs["sku"]]["availability"]["shipToLocationAvailability"]["quantity"] = kwargs["quantity"]
    monkeypatch.setattr(ebay.FakeEbayInventoryAdapter, "update_quantity", partial)
    result = q.update_quantity(allocation, payload(allocation, 4))
    assert result["state"] == "unknown" and not result["can_write"]
    allocation.refresh_from_db()
    assert q.check_quantity(allocation)["state"] == "unknown"


def test_refund_cancellation_payload_never_restocks(allocation):
    row = sale(allocation.item, 1, channel="ebay_au", ebay_order_id="refund", ebay_line_item_id="one")
    row.channel_data = {"refund": True, "cancelled": True}
    row.save()
    assert q.stock_basis(allocation.item, "sandbox")["remaining"] == 4
    assert q.item_quantity_state(allocation.item, "sandbox")["target"] == 4


def test_second_live_offer_is_blocked_and_unique_allocation_backstop(allocation):
    draft = ListingDraft.objects.create(item=allocation.item, title="Relist", quantity=1)
    checks, _ = q.quantity_checks(draft)
    assert {"stock_already_listed", "stock_allocated"} <= {c["key"] for c in checks}
    with pytest.raises(IntegrityError), transaction.atomic():
        EbayListingAllocation.objects.create(item=allocation.item, draft=draft, environment="sandbox", sku=allocation.sku, allocation_quantity=1)


def test_quantity_diagnostics_model_boundary_rejects_secrets(allocation):
    fields = dict(allocation=allocation, stock_revision=0, allocation_revision=0, stock_fingerprint="0" * 64, requested_quantity=1)
    with pytest.raises(ValidationError):
        EbayQuantityUpdate.objects.create(**fields, diagnostic={"token": "synthetic-private-value"})
    attempt = EbayQuantityUpdate.objects.create(**fields, diagnostic=diagnostic("inventory.quantity", status=403))
    with pytest.raises(ValidationError):
        EbayQuantityUpdate.objects.filter(pk=attempt.pk).update(diagnostic={"raw_body": "synthetic-private-value"})
    with pytest.raises(ValidationError):
        EbayQuantityUpdate.objects.bulk_create([EbayQuantityUpdate(**fields, diagnostic={"headers": {"Authorization": "synthetic-private-value"}})])


def test_quantity_http_payload_contains_no_price_or_published_fields(monkeypatch):
    from apps.ebay import adapters
    request = Mock(return_value={"responses": [{"sku": "owned", "offerId": "offer", "statusCode": 200}]})
    monkeypatch.setattr(adapters, "_request_json", request)
    adapters.HttpEbayInventoryAdapter(environment="sandbox").update_quantity(access_token="synthetic", sku="owned", offer_id="offer", quantity=3)
    sent = json.loads(request.call_args.kwargs["data"])
    assert sent == {"requests": [{"sku": "owned", "shipToLocationAvailability": {"quantity": 3}, "offers": [{"offerId": "offer", "availableQuantity": 3}]}]}
    assert request.call_count == 1 and request.call_args.kwargs["timeout_seconds"] <= 60


def test_local_quantity_get_and_hub_never_fetch_or_write(item, django_user_model, monkeypatch):
    user = django_user_model.objects.create_user(username="quantity")
    client = APIClient(); client.force_authenticate(user)
    forbidden = Mock(side_effect=AssertionError("No network on load"))
    monkeypatch.setattr(q, "get_access_token", forbidden)
    monkeypatch.setattr(q.ebay, "get_ebay_inventory_adapter", forbidden)
    assert client.get(f"/api/items/{item.pk}/ebay-quantity/").status_code == 200
    assert client.get("/api/ebay/hub/").status_code == 200
    assert not forbidden.called and not EbayListingAllocation.objects.exists()


def test_simultaneous_quantity_updates_one_write_file_sqlite_and_postgres(concurrent_draft, monkeypatch):
    draft = publish(concurrent_draft)
    using = draft._state.db
    monkeypatch.setattr(q, "get_access_token", lambda **kwargs: "synthetic")
    allocation = EbayListingAllocation.objects.using(using).get(draft=draft)
    q.check_quantity(allocation)
    allocation.refresh_from_db()
    request = payload(allocation, 1)
    calls = []
    original = ebay.FakeEbayInventoryAdapter.update_quantity
    def send(self, **kwargs):
        calls.append(kwargs["quantity"]); return original(self, **kwargs)
    monkeypatch.setattr(ebay.FakeEbayInventoryAdapter, "update_quantity", send)
    gate = Barrier(2)
    def worker():
        try:
            gate.wait(timeout=10)
            return q.update_quantity(EbayListingAllocation.objects.using(using).get(pk=allocation.pk), request)
        except (WorkflowError, DatabaseError):
            return "conflict"
        finally:
            connections[using].close()
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda _: worker(), range(2)))
    assert calls == [1]
    assert EbayQuantityUpdate.objects.using(using).count() == 1


def test_local_and_ebay_sale_during_update_requires_reconciliation(allocation, monkeypatch):
    original = ebay.FakeEbayInventoryAdapter.update_quantity
    calls = []
    def concurrent_sales(self, **kwargs):
        calls.append(kwargs["quantity"])
        sale(allocation.item, 1)
        sale(allocation.item, 1, channel="ebay_au", ebay_order_id="concurrent", ebay_line_item_id="line")
        original(self, **kwargs)
    monkeypatch.setattr(ebay.FakeEbayInventoryAdapter, "update_quantity", concurrent_sales)
    result = q.update_quantity(allocation, payload(allocation, 4))
    assert result["state"] == "unknown" and not result["can_write"]
    assert q.stock_basis(allocation.item, "sandbox")["remaining"] == 3
    ebay.FakeEbayInventoryAdapter.inventory_items[allocation.sku]["availability"]["shipToLocationAvailability"]["quantity"] = 3
    ebay.FakeEbayInventoryAdapter.offers[allocation.offer_id]["availableQuantity"] = 3
    allocation.refresh_from_db()
    assert not q.check_quantity(allocation)["attempt_id"]
    assert calls == [4]


def test_order_which_cannot_fit_after_local_sale_is_kept_pending(allocation):
    from apps.ebay.order_sync import OrderLine, FeeMapping, _import_line
    from decimal import Decimal
    sale(allocation.item, 4)
    line = OrderLine(order_id="oversold", line_item_id="one", sku=allocation.sku, quantity=2,
        line_price=Decimal("20.00"), sale_date=timezone.localdate(), buyer_region="AU", raw={})
    fee = FeeMapping(amount=None, status="estimated_or_unmapped", transaction_id="", breakdown={}, snapshot={})
    assert _import_line(environment="sandbox", line=line, fee=fee) == "staged"
    assert EbayOrderStaging.objects.get().quantity == 2
    assert q.stock_basis(allocation.item, "sandbox")["remaining"] == 0


def test_sale_after_listing_review_blocks_stage(draft):
    from apps.ebay.staging import stage_draft
    review = prepare_review(draft)
    sale(draft.item, 1)
    with pytest.raises(WorkflowError):
        stage_draft(draft, review_id=review.pk)
    assert not EbayListingAllocation.objects.exists() and not ebay.FakeEbayInventoryAdapter.inventory_items


def test_general_item_save_does_not_reset_stock_revision(allocation):
    stale = InventoryItem.objects.get(pk=allocation.item_id)
    sale(allocation.item, 1)
    revision = InventoryItem.objects.get(pk=allocation.item_id).stock_revision
    stale.title = "Human title change"
    stale.save()
    assert InventoryItem.objects.get(pk=stale.pk).stock_revision >= revision


def test_mismatch_after_timeout_not_assumed_failure_or_retried(allocation, monkeypatch):
    def timeout(self, **kwargs):
        raise TimeoutError("synthetic")
    monkeypatch.setattr(ebay.FakeEbayInventoryAdapter, "update_quantity", timeout)
    q.update_quantity(allocation, payload(allocation, 4))
    allocation.refresh_from_db()
    EbayQuantityUpdate.objects.update(request_sent_at=timezone.now() - timedelta(minutes=11))
    result = q.check_quantity(allocation)
    assert result["attempt_id"] and result["state"] == "unknown"
    assert EbayQuantityUpdate.objects.get().outcome == "unknown"


def test_quantity_api_refuses_listing_fields(allocation, django_user_model):
    client = APIClient(); client.force_authenticate(django_user_model.objects.create_user(username="qty-api"))
    url = f"/api/ebay/allocations/{allocation.pk}/update/"
    assert client.post(url, {**payload(allocation), "price": "123"}, format="json").status_code == 400
    assert not EbayQuantityUpdate.objects.exists()


def test_publish_requires_the_staged_allocation_not_just_remaining_stock(draft):
    from apps.ebay.review import live_validation
    staged = stage(draft)
    EbayListingAllocation.objects.filter(draft=staged).update(allocation_quantity=0)
    result = live_validation(staged)
    assert "allocation_unverified" in {row["key"] for row in result["publish_checks"]}
    with pytest.raises(WorkflowError):
        publish(staged)
    assert ebay.FakeEbayInventoryAdapter.publish_count == 0


def test_simultaneous_local_and_ebay_stock_deduction_file_sqlite_and_postgres(concurrent_draft):
    using = concurrent_draft._state.db
    owned = concurrent_draft.item
    owned.quantity_total = 2
    owned.save(using=using)
    gate = Barrier(2)
    def worker(channel):
        try:
            gate.wait(timeout=10)
            return sale(owned, 1, channel=channel)
        finally:
            connections[using].close()
    with ThreadPoolExecutor(max_workers=2) as pool:
        rows = list(pool.map(worker, ["manual", "ebay_au"]))
    assert len(rows) == 2
    assert q.stock_basis(owned, "sandbox")["remaining"] == 0
    assert SaleRecord.objects.using(using).filter(item=owned).count() == 2


def test_late_completion_cannot_overwrite_newer_attempt(allocation):
    import uuid
    basis = q.stock_basis(allocation.item, "sandbox")
    attempt = EbayQuantityUpdate.objects.create(allocation=allocation, stock_revision=basis["stock_revision"], allocation_revision=allocation.revision,
        stock_fingerprint=basis["fingerprint"], requested_quantity=3, outcome="definite_failure")
    newer = uuid.uuid4()
    EbayListingAllocation.objects.filter(pk=allocation.pk).update(current_attempt=newer)
    before = EbayListingAllocation.objects.values().get(pk=allocation.pk)
    assert not q._finish(allocation, attempt, 3, 3, basis, reconcile=True)
    assert before == EbayListingAllocation.objects.values().get(pk=allocation.pk)


def test_manual_takedown_releases_allocation_only_without_unresolved_attempt(allocation):
    row = allocation.channel_listing
    row.ended_at = timezone.now()
    row.save(update_fields=["ended_at", "updated_at"])
    allocation.refresh_from_db()
    assert allocation.closed_at == row.ended_at
    assert q.item_quantity_state(allocation.item, "sandbox")["state"] == "not_listed"


def test_partial_quantity_response_diagnostics_are_sanitized_and_not_definite(monkeypatch):
    from apps.ebay import adapters
    request = Mock(return_value={"responses": [{"sku": "owned", "offerId": "offer", "statusCode": 400,
        "errors": [{"errorId": 25004, "domain": "API_INVENTORY", "message": "synthetic-private-value", "parameters": [{"name": "quantity", "value": "synthetic-private-value"}]}]}]})
    monkeypatch.setattr(adapters, "_request_json", request)
    with pytest.raises(ebay.EbayUnavailable) as caught:
        adapters.HttpEbayInventoryAdapter(environment="sandbox").update_quantity(access_token="synthetic", sku="owned", offer_id="offer", quantity=3)
    value = caught.value.diagnostic
    assert value["http_status"] is None and value["issues"][0]["error_id"] == 25004
    assert "synthetic-private-value" not in json.dumps(value)


def test_other_format_remote_live_offer_blocks_stage_even_without_local_tracking(draft):
    from apps.ebay.staging import stage_draft
    ebay.FakeEbayInventoryAdapter.offers["other-format"] = {"offerId": "other-format", "sku": draft.item.sku,
        "marketplaceId": "EBAY_AU", "format": "AUCTION", "status": "PUBLISHED", "listingId": "another-listing"}
    with pytest.raises(WorkflowError, match="another live"):
        stage_draft(draft, review_id=prepare_review(draft).pk)
    assert not ebay.FakeEbayInventoryAdapter.inventory_items
    assert ebay.FakeEbayInventoryAdapter.publish_count == 0
