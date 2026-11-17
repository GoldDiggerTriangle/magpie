"""Attempt-fenced publish state machine. Network I/O never holds a DB transaction."""
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from datetime import timedelta
import uuid

from django.db import DatabaseError, OperationalError, close_old_connections, connections, transaction
from django.db.models import F, Q
from django.utils import timezone

import integrations.ebay as ebay
from apps.audit.services import record
from apps.ebay.review import eps_checks, field_fingerprint, fresh_draft, live_validation, mapping, reviewed, text, _offer_state
from apps.ebay.services import get_access_token
from apps.ebay.workflow_errors import WorkflowError, provider_error
from apps.inventory.models import InventoryItem
from apps.listing.draft_status import IN_FLIGHT_DRAFT_STATUSES, read_only_draft_filter
from apps.listing.models import ChannelListing, ListingDraft
from apps.listing.public_urls import ebay_listing_url


PUBLISH_TIMEOUT_SECONDS = 60
STALE_AFTER = timedelta(minutes=10)


def mutable_rows(using="default"):
    return ListingDraft.objects.using(using).exclude(read_only_draft_filter()).exclude(status__in=IN_FLIGHT_DRAFT_STATUSES).exclude(staging_state="in_progress")


def recover_stale(*, draft_id=None, using="default", now=None):
    cutoff = (now or timezone.now()) - STALE_AFTER
    candidates = ListingDraft.objects.using(using).filter(status="publishing").exclude(read_only_draft_filter()).filter(Q(publish_started_at__lt=cutoff) | Q(publish_started_at__isnull=True, updated_at__lt=cutoff))
    if draft_id:
        candidates = candidates.filter(pk=draft_id)
    count = 0
    for pk, attempt in candidates.values_list("pk", "publish_attempt"):
        count += ListingDraft.objects.using(using).filter(pk=pk, status="publishing", publish_attempt=attempt).filter(Q(publish_started_at__lt=cutoff) | Q(publish_started_at__isnull=True, updated_at__lt=cutoff)).update(
            status="publish_unknown", updated_at=timezone.now(), publish_error={"kind": "interrupted", "message": "Publish was interrupted. Reconcile; do not retry."})
    return count


def claim(draft, review):
    using = draft._state.db or "default"
    recover_stale(draft_id=draft.pk, using=using)
    attempt = uuid.uuid4()
    try:
        changed = mutable_rows(using).filter(pk=draft.pk, updated_at=review.draft_revision,
            staged_fingerprint=review.staged_fingerprint, staging_state="verified",
            channel_data__offer_id=review.offer_id,
            publish_reviews__pk=review.pk, publish_reviews__expires_at__gt=timezone.now(),
            item__updated_at=review.snapshot["item_revision"], item__stock_revision=review.snapshot["stock_revision"]).update(
                # F(status) is evaluated by this same UPDATE, never an earlier read.
                publish_prior_status=F("status"), status="publishing", publish_attempt=attempt,
                publish_started_at=timezone.now(), publish_call_started_at=None, publish_error={},
                publish_review=review, updated_at=timezone.now())
    except OperationalError:
        changed = 0
    if changed != 1:
        raise WorkflowError("already_publishing", "Already publishing, or the reviewed revision changed. Reload and review again.")
    record(actor=review.actor, action="ebay.publish.attempted", target_type="listing_draft", target_id=draft.pk,
           payload={"attempt": str(attempt), "review": str(review.pk), "offer_id": review.offer_id}, using=using)
    return attempt


def mark_unknown(pk, attempt, error, *, using="default"):
    return ListingDraft.objects.using(using).filter(pk=pk, publish_attempt=attempt, status__in=IN_FLIGHT_DRAFT_STATUSES).update(status="publish_unknown", publish_error=error, updated_at=timezone.now())


def finish_failure(pk, attempt, error, *, using="default", actor=None):
    with transaction.atomic(using=using):
        changed = ListingDraft.objects.using(using).filter(pk=pk, publish_attempt=attempt, status__in=IN_FLIGHT_DRAFT_STATUSES).exclude(publish_prior_status="").update(status=F("publish_prior_status"), publish_error=error, updated_at=timezone.now())
        if changed:
            record(actor=actor, action="ebay.publish.failed", target_type="listing_draft", target_id=pk,
                   payload={"attempt": str(attempt), **error}, using=using)
    return changed


def record_success(pk, attempt, listing_id, *, using="default", actor=None):
    with transaction.atomic(using=using):
        # This write fence serializes concurrent completions/reconciles on SQLite
        # too. Only the winner can create the listing, update the item and audit.
        rows = ListingDraft.objects.using(using).filter(pk=pk, publish_attempt=attempt, status__in=IN_FLIGHT_DRAFT_STATUSES).exclude(read_only_draft_filter())
        if rows.update(updated_at=F("updated_at")) != 1:
            return False
        draft = fresh_draft(pk, using)
        data = dict(draft.channel_data or {})
        now = timezone.now()
        data.update(listing_id=listing_id, published_at=now.isoformat(), last_ebay_error="")
        if rows.update(status="published", channel_data=data, publish_error={}, updated_at=now) != 1:
            return False
        listing = ChannelListing.objects.using(using).create(item=draft.item, channel="ebay", external_listing_id=listing_id,
            source_listing_draft=draft, listed_at=now, url=ebay_listing_url(listing_id), note="Created from reviewed Magpie publish.")
        from apps.ebay.quantity import mark_live
        mark_live(draft, listing)
        InventoryItem.objects.using(using).filter(pk=draft.item_id).exclude(status__in=["sold", "archived"]).update(status="listed", updated_at=now)
        record(actor=actor, action="ebay.publish.succeeded", target_type="listing_draft", target_id=pk,
               payload={"attempt": str(attempt), "listing_id": listing_id, "offer_id": data.get("offer_id")}, using=using)
    return True


def _publish_worker(pk, attempt, access, inventory, *, using, actor_label):
    close_old_connections()
    try:
        draft = fresh_draft(pk, using)
        review = draft.publish_review
        current = live_validation(draft, actor=None)
        if not review or current["field_fingerprint"] != review.field_fingerprint or current["validation_fingerprint"] != review.validation_fingerprint or current["checks"] or current["publish_checks"] or draft.item.quantity_remaining != review.snapshot["remaining_stock"]:
            finish_failure(pk, attempt, {"kind": "review_changed", "message": "Photos or listing content changed; update and review again."}, using=using, actor=actor_label)
            return
        # An interrupted/queued request must not send after stale recovery or
        # reconcile. Crossing this fenced barrier means a timeout is NOT a cancel.
        started = ListingDraft.objects.using(using).filter(pk=pk, status="publishing", publish_attempt=attempt).update(publish_call_started_at=timezone.now())
        if started != 1:
            return
        try:
            listing_id = inventory.publish_offer(access_token=access, offer_id=review.offer_id)
            if not isinstance(listing_id, str) or not listing_id:
                raise RuntimeError("Unconfirmed publish response")
        except Exception as exc:
            error = provider_error(exc, "publishOffer")
            if error["kind"] == "definite_failure":
                finish_failure(pk, attempt, error, using=using, actor=actor_label)
            else:
                mark_unknown(pk, attempt, error, using=using)
            return
        try:
            record_success(pk, attempt, listing_id, using=using, actor=actor_label)
        except Exception:
            # A remote success + failed local commit is never permission to send
            # publishOffer again. If the DB is down, publishing itself still blocks.
            try:
                mark_unknown(pk, attempt, {"kind": "persistence_failed", "message": "eBay may be live; local save failed. Reconcile, never republish."}, using=using)
            except DatabaseError:
                pass
    finally:
        connections[using].close()


def publish_draft(draft, *, review_id=None, confirm_sku="", actor=None, mode="full"):
    using = draft._state.db or "default"
    recover_stale(draft_id=draft.pk, using=using)
    draft = fresh_draft(draft.pk, using)
    if draft.status in IN_FLIGHT_DRAFT_STATUSES:
        raise WorkflowError("already_publishing", "Already publishing or outcome unknown. Reconcile before any new attempt.")
    if draft.is_read_only or mapping(draft.channel_data).get("listing_id"):
        raise WorkflowError("already_published", "Published history cannot be published again.", status=400)
    review, result = reviewed(draft, review_id, actor=actor, for_publish=True)
    if mode != review.mode or (mode == "full" and confirm_sku != draft.item.sku):
        raise WorkflowError("confirmation", "Type the exact SKU for full publish, or use the explicitly reviewed quick path.", status=400)
    attempt = claim(draft, review)
    try:
        access = get_access_token(actor=actor)
    except Exception as exc:
        from apps.ebay.diagnostics import public_diagnostic, safe_exception, safe_message
        value = public_diagnostic(safe_exception(exc, "oauth.refresh"))
        message = safe_message(exc, "oauth.refresh") + " No publish was sent."
        finish_failure(draft.pk, attempt, {"kind": "connection", "message": message, "diagnostic": value}, using=using, actor=actor)
        raise WorkflowError("connection", message, status=503, diagnostic=value) from None
    inventory = ebay.get_ebay_inventory_adapter()
    label = actor.get_username() if hasattr(actor, "get_username") else str(actor or "")
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="magpie-manual-publish")
    future = executor.submit(_publish_worker, draft.pk, attempt, access, inventory, using=using, actor_label=label)
    try:
        future.result(timeout=PUBLISH_TIMEOUT_SECONDS)
    except FutureTimeout:
        mark_unknown(draft.pk, attempt, {"kind": "timeout", "message": "60 second publish deadline exceeded. This is not cancellation; reconcile."}, using=using)
    except Exception:
        mark_unknown(draft.pk, attempt, {"kind": "interrupted", "message": "Publish worker interrupted. Reconcile; do not retry."}, using=using)
    finally:
        executor.shutdown(wait=False)
    current = fresh_draft(draft.pk, using)
    if current.status == "published":
        return current
    if current.status in IN_FLIGHT_DRAFT_STATUSES:
        raise WorkflowError("publish_unknown", "Publish outcome is unknown. Do not retry; reconcile the offer.", status=503)
    raise WorkflowError("publish_failed", mapping(current.publish_error).get("message", "Publish was rejected. Review again."), status=400)


def reconcile_draft(draft, *, actor=None):
    using = draft._state.db or "default"
    recover_stale(draft_id=draft.pk, using=using)
    draft = fresh_draft(draft.pk, using)
    if draft.status == "published":
        return draft
    if draft.status not in IN_FLIGHT_DRAFT_STATUSES or not draft.publish_attempt:
        raise WorkflowError("reconcile_state", "No tracked unknown publish attempt exists for this draft.")
    attempt = draft.publish_attempt
    try:
        offer = ebay.get_ebay_inventory_adapter().get_offer(access_token=get_access_token(actor=actor), offer_id=text(mapping(draft.channel_data).get("offer_id")))
    except Exception:
        mark_unknown(draft.pk, attempt, {"kind": "reconcile_unavailable", "message": "Offer is missing or unreachable; outcome remains unknown."}, using=using)
        return fresh_draft(draft.pk, using)
    state, listing_id = _offer_state(offer)
    if offer.get("sku") != draft.item.sku:
        mark_unknown(draft.pk, attempt, {"kind": "ambiguous_offer", "message": "Offer identity is ambiguous; outcome remains unknown."}, using=using)
    elif state == "PUBLISHED" and listing_id:
        try:
            record_success(draft.pk, attempt, listing_id, using=using, actor=actor)
        except Exception:
            mark_unknown(draft.pk, attempt, {"kind": "persistence_failed", "message": "Could not record remote success; reconcile again, never republish."}, using=using)
    elif state == "UNPUBLISHED" and not listing_id and draft.publish_call_started_at is None and draft.publish_review_id and draft.publish_prior_status:
        # The pre-send barrier is closed by this conditional status update. A
        # worker that never crossed it cannot wake up later and send the request.
        ListingDraft.objects.using(using).filter(pk=draft.pk, publish_attempt=attempt, status__in=IN_FLIGHT_DRAFT_STATUSES,
            publish_call_started_at__isnull=True).update(status=F("publish_prior_status"), publish_error={}, updated_at=timezone.now())
    else:
        mark_unknown(draft.pk, attempt, {"kind": "unresolved_in_flight", "message": "A timeout is not cancellation. No conclusive resolution; outcome remains unknown."}, using=using)
    return fresh_draft(draft.pk, using)


def publish_health(using="default"):
    return [{"id": str(row.pk), "sku": row.item.sku, "status": row.status,
             "started_at": row.publish_started_at.isoformat() if row.publish_started_at else None,
             "attempt": str(row.publish_attempt) if row.publish_attempt else None,
             "message": mapping(row.publish_error).get("message", "Publishing; reconcile if interrupted.")}
            for row in ListingDraft.objects.using(using).filter(status__in=IN_FLIGHT_DRAFT_STATUSES).select_related("item")]
