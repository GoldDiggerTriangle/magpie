"""Explicit allocation and quantity-only updates. Reads never initialise state."""
from datetime import timedelta
import hashlib
import json

from django.db import IntegrityError, OperationalError, transaction
from django.db.models import F
from django.utils import timezone

import integrations.ebay as ebay
from apps.audit.services import record
from apps.ebay.diagnostics import safe_exception
from apps.ebay.models import EbayListingAllocation, EbayOrderDuplicateCandidate, EbayOrderStaging, EbayQuantityUpdate
from apps.ebay.services import get_access_token
from apps.ebay.workflow_errors import WorkflowError
from apps.inventory.models import InventoryItem
from apps.listing.models import ChannelListing
from apps.sales.models import SaleRecord

UNRESOLVED = ("claimed", "in_flight", "unknown")


def order_stock_fence(sku, *, using="default"):
    rows = InventoryItem.objects.using(using)
    if sku and rows.filter(sku=sku).update(stock_revision=F("stock_revision") + 1):
        return
    # An unattributable order can affect any proposed increase. Invalidate all
    # stock reviews conservatively, without pretending which item it consumed.
    rows.update(stock_revision=F("stock_revision") + 1)


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def stock_basis(item, environment):
    using = item._state.db or "default"
    item = InventoryItem.objects.using(using).get(pk=item.pk)
    sales = list(SaleRecord.objects.using(using).filter(item=item).order_by("id"))
    by_id = {s.pk: s for s in sales}
    superseded = {s.corrected_from_id for s in sales if s.corrected_from_id}
    events, identities, roots = {}, {}, {}
    for sale in sales:
        if sale.pk in superseded:
            continue
        root = sale
        seen = set()
        chain = [sale]
        while root.corrected_from_id in by_id and root.pk not in seen:
            seen.add(root.pk)
            root = by_id[root.corrected_from_id]
            chain.append(root)
        key = "sale:" + str(root.pk)
        roots[sale.pk] = key
        for row in chain:
            roots[row.pk] = key
            if row.ebay_order_id and row.ebay_line_item_id:
                identities[(row.ebay_order_id, row.ebay_line_item_id)] = key
        is_ebay = any(bool(row.ebay_order_id and row.ebay_line_item_id) or row.channel == "ebay_au" or row.provenance == "ebay_sync" for row in chain)
        events[key] = {"quantity": sale.quantity, "ebay": is_ebay}
        if sale.ebay_order_id and sale.ebay_line_item_id:
            identities[(sale.ebay_order_id, sale.ebay_line_item_id)] = key
    sold = sum(e["quantity"] for e in events.values())
    pending, unlinked, queue = 0, 0, []
    duplicates = EbayOrderDuplicateCandidate.objects.using(using).filter(environment=environment).order_by("id")
    for row in duplicates:
        identity = (row.ebay_order_id, row.ebay_line_item_id)
        if row.item_id == item.pk and row.manual_sale_id in roots and row.status in {"pending", "linked"}:
            key = roots[row.manual_sale_id]
            identities[identity] = key
            events[key]["ebay"] = True
            queue.append(["duplicate", str(row.pk), row.status, row.quantity])
    known_skus = set(InventoryItem.objects.using(using).values_list("sku", flat=True))
    for row in EbayOrderStaging.objects.using(using).filter(environment=environment, status="pending").order_by("id"):
        if row.sku != item.sku and row.sku in known_skus:
            continue
        identity = (row.ebay_order_id, row.ebay_line_item_id)
        queue.append(["staging", str(row.pk), row.sku, row.quantity])
        if row.sku != item.sku:
            unlinked += 1
            continue
        if identity not in identities:
            key = "order:" + ":".join(identity)
            if key not in events:
                events[key] = {"quantity": row.quantity, "ebay": True}
                pending += row.quantity
            identities[identity] = key
    remaining = max(item.quantity_total - sold - pending, 0) if item.disposition != "scrapped" else 0
    value = {"stock_revision": item.stock_revision, "total": item.quantity_total, "sold": sold,
             "remaining": remaining, "pending_units": pending, "unlinked_orders": unlinked,
             "events": events, "queue": queue}
    value["fingerprint"] = _digest(value)
    return value


def allocation_target(allocation, basis):
    previous = allocation.allocation_basis.get("events", {})
    consumed = sum(max(e["quantity"] - previous.get(key, {}).get("quantity", 0), 0)
                   for key, e in basis["events"].items() if e["ebay"])
    return max(min(allocation.allocation_quantity - consumed, basis["remaining"]), 0)


def quantity_checks(draft):
    from apps.ebay.adapters import effective_environment
    environment = effective_environment()
    using = draft._state.db or "default"
    basis = stock_basis(draft.item, environment)
    errors = []
    def add(key, message):
        errors.append({"key": key, "message": message, "field": "quantity", "level": "fail"})
    if draft.quantity <= 0 or draft.quantity > basis["remaining"]:
        add("available_stock", f"Listing quantity exceeds available stock ({basis['remaining']} remaining after pending orders).")
    if basis["unlinked_orders"]:
        add("unlinked_stock", "Resolve unlinked eBay orders before allocating stock to a new offer.")
    active = ChannelListing.objects.using(using).filter(item=draft.item, channel="ebay", ended_at__isnull=True)
    if active.exclude(source_listing_draft=draft).exists():
        add("stock_already_listed", "This stock already has an active eBay listing. End/verify it before another offer.")
    allocations = EbayListingAllocation.objects.using(using).filter(item=draft.item, environment=environment, closed_at__isnull=True)
    if allocations.exclude(draft=draft).exists():
        add("stock_allocated", "Stock is reserved by another eBay offer; resolve that allocation first.")
    allocation = allocations.filter(draft=draft).first()
    if allocation and allocation.current_attempt and allocation.attempts.filter(pk=allocation.current_attempt, outcome__in=UNRESOLVED).exists():
        add("quantity_unknown", "Reconcile the quantity update before staging or publishing.")
    return errors, basis


def reserve_for_stage(draft, review):
    from apps.ebay.adapters import effective_environment
    environment = effective_environment()
    using = draft._state.db or "default"
    with transaction.atomic(using=using):
        changed = InventoryItem.objects.using(using).filter(pk=draft.item_id, stock_revision=review.snapshot["stock_revision"]).update(stock_revision=F("stock_revision"))
        if changed != 1:
            raise WorkflowError("stock_changed", "Stock changed since review. Review again.")
        checks, basis = quantity_checks(draft)
        if checks or basis["fingerprint"] != review.snapshot["stock_fingerprint"]:
            raise WorkflowError("stock_changed", checks[0]["message"] if checks else "Stock/order queue changed since review.")
        try:
            allocation, created = EbayListingAllocation.objects.using(using).get_or_create(draft=draft, environment=environment, marketplace="EBAY_AU",
                defaults={"item": draft.item, "sku": draft.item.sku, "allocation_quantity": draft.quantity, "allocation_basis": {"events": basis["events"]}})
        except IntegrityError:
            raise WorkflowError("stock_allocated", "Stock is already allocated to another eBay offer.") from None
        if not created:
            EbayListingAllocation.objects.using(using).filter(pk=allocation.pk).update(allocation_quantity=draft.quantity,
                allocation_basis={"events": basis["events"]}, revision=F("revision") + 1, verification_state="unverified", closed_at=None)
    return allocation


def mark_live(draft, listing):
    EbayListingAllocation.objects.using(draft._state.db or "default").filter(draft=draft, closed_at__isnull=True).update(channel_listing=listing,
        offer_id=str(draft.channel_data.get("offer_id") or ""), listing_id=listing.external_listing_id,
        verification_state="unverified", last_inventory_available=None, last_offer_available=None, verified_at=None)


def item_quantity_state(item, environment):
    using = item._state.db or "default"
    listings = list(ChannelListing.objects.using(using).filter(item=item, channel="ebay", ended_at__isnull=True))
    allocation = EbayListingAllocation.objects.using(using).filter(item=item, environment=environment, closed_at__isnull=True).exclude(channel_listing=None).first()
    if allocation is None:
        return {"item_id": str(item.pk), "sku": item.sku, "state": "allocation_not_recorded" if listings else "not_listed",
                "label": "Allocation not recorded" if listings else "Not listed on eBay", "can_write": False, "urgent": False}
    basis = stock_basis(item, environment)
    target = allocation_target(allocation, basis)
    attempt = allocation.attempts.filter(pk=allocation.current_attempt, outcome__in=UNRESOLVED).first() if allocation.current_attempt else None
    old = min(allocation.last_inventory_available, allocation.last_offer_available) if allocation.last_inventory_available is not None and allocation.last_offer_available is not None else None
    urgent = target < (old if old is not None else allocation.allocation_quantity)
    state = "unknown" if attempt else "take_down" if basis["remaining"] == 0 else "update_required" if urgent else allocation.verification_state
    return {"item_id": str(item.pk), "sku": item.sku, "allocation_id": str(allocation.pk), "state": state,
        "label": "Check quantity result; do not retry" if attempt else "Stock exhausted - take down the listing" if state == "take_down" else f"Update eBay: {old if old is not None else '?'} -> {target}" if urgent else "eBay stock allocation",
        "urgent": urgent or bool(attempt), "can_write": old is not None and not attempt and basis["remaining"] > 0 and allocation.channel_listing.ended_at is None,
        "allocated": allocation.allocation_quantity, "target": target, "inventory_available": allocation.last_inventory_available,
        "offer_available": allocation.last_offer_available, "verified_at": allocation.verified_at,
        "remaining": basis["remaining"], "pending_units": basis["pending_units"], "unlinked_orders": basis["unlinked_orders"],
        "stock_revision": basis["stock_revision"], "stock_fingerprint": basis["fingerprint"], "allocation_revision": allocation.revision,
        "attempt_id": str(attempt.pk) if attempt else None}


def _read_remote(allocation, inventory, access):
    item = inventory.get_inventory_item(access_token=access, sku=allocation.sku)
    offer = inventory.get_offer(access_token=access, offer_id=allocation.offer_id)
    listing = offer.get("listing") or {}
    listing_id = offer.get("listingId") or listing.get("listingId")
    if offer.get("sku") != allocation.sku or offer.get("status") != "PUBLISHED" or str(listing_id or "") != allocation.listing_id:
        raise WorkflowError("remote_quantity", "The recorded live offer cannot be verified; no quantity write is allowed.")
    a = (item.get("availability") or {}).get("shipToLocationAvailability", {}).get("quantity")
    b = offer.get("availableQuantity")
    if type(a) is not int or type(b) is not int or a < 0 or b < 0:
        raise WorkflowError("remote_quantity", "Inventory/offer available quantities were not both returned. No quantity is inferred.")
    return a, b


def check_quantity(allocation, *, actor=None):
    if not allocation.channel_listing_id or allocation.closed_at:
        raise WorkflowError("not_live", "No active recorded allocation to check.")
    access = get_access_token(actor=actor)
    inventory = ebay.get_ebay_inventory_adapter()
    a, b = _read_remote(allocation, inventory, access)
    basis = stock_basis(allocation.item, allocation.environment)
    attempt = allocation.attempts.filter(pk=allocation.current_attempt, outcome__in=UNRESOLVED).first() if allocation.current_attempt else None
    if attempt:
        if not attempt.completed_at and (attempt.request_sent_at or attempt.created_at) > timezone.now() - timedelta(minutes=10):
            raise WorkflowError("in_flight", "Quantity request may still be in flight. Wait ten minutes before reconciling; a timeout is not cancellation.")
        _finish(allocation, attempt, a, b, basis, reconcile=True)
        if allocation.channel_listing.ended_at:
            EbayListingAllocation.objects.using(allocation._state.db or "default").filter(pk=allocation.pk, current_attempt__isnull=True).update(closed_at=allocation.channel_listing.ended_at)
    else:
        # Observation never raises the intended allocation. A lower remote
        # quantity may be an eBay sale not imported locally yet.
        anchor = min(allocation_target(allocation, basis), a, b)
        EbayListingAllocation.objects.using(allocation._state.db or "default").filter(pk=allocation.pk, revision=allocation.revision, current_attempt=allocation.current_attempt).update(
            last_inventory_available=a, last_offer_available=b, verified_at=timezone.now(), revision=F("revision") + 1,
            allocation_quantity=anchor, allocation_basis={"events": basis["events"]}, verification_state="verified")
    return item_quantity_state(allocation.item, allocation.environment)


def _finish(allocation, attempt, a, b, basis, *, reconcile=False):
    using = allocation._state.db or "default"
    before = allocation.allocation_basis.get("events", {})
    consumed = sum(max(e["quantity"] - before.get(k, {}).get("quantity", 0), 0) for k, e in basis["events"].items() if e["ebay"])
    expected = max(attempt.requested_quantity - consumed, 0) if reconcile else attempt.requested_quantity
    stable = basis["fingerprint"] == attempt.stock_fingerprint or reconcile
    verified = stable and a == b == expected
    with transaction.atomic(using=using):
        if InventoryItem.objects.using(using).filter(pk=allocation.item_id, stock_revision=basis["stock_revision"]).update(stock_revision=F("stock_revision")) != 1:
            verified = False
        rows = EbayListingAllocation.objects.using(using).filter(pk=allocation.pk, current_attempt=attempt.pk)
        if rows.update(revision=F("revision") + 1, last_inventory_available=a, last_offer_available=b,
                       verification_state="verified" if verified else "unknown") != 1:
            return False
        changes = {"outcome": "verified" if verified else "unknown", "inventory_after": a, "offer_after": b,
                   "stock_revision_after": basis["stock_revision"], "post_stock_fingerprint": basis["fingerprint"], "completed_at": timezone.now()}
        if verified:
            changes["completed_at"] = timezone.now()
            rows.update(current_attempt=None, allocation_quantity=expected, allocation_basis={"events": basis["events"]}, verified_at=timezone.now())
        EbayQuantityUpdate.objects.using(using).filter(pk=attempt.pk, outcome__in=UNRESOLVED).update(**changes)
        record(actor=attempt.actor, action="ebay.quantity.verified" if verified else "ebay.quantity.unknown", target_type="ebay_quantity_update", target_id=attempt.pk,
               payload={"inventory_available": a, "offer_available": b, "requested_quantity": attempt.requested_quantity}, using=using)
    if verified:
        from apps.ebay.connection_health import observe_begin, observe_finish
        # Recovery is based on this operation's successful GET readback, not an
        # unrelated Inventory probe, and does not claim the timed-out POST won.
        observe_finish(observe_begin("inventory.quantity"), status=200)
    return verified


def update_quantity(allocation, payload, *, actor=None):
    using = allocation._state.db or "default"
    current = item_quantity_state(allocation.item, allocation.environment)
    wanted = payload.get("quantity")
    if type(wanted) is not int or wanted <= 0 or wanted > current.get("remaining", 0):
        raise WorkflowError("quantity", "Choose a positive quantity within remaining stock. At zero, use the explicit take-down checklist.", status=400)
    if not current.get("can_write") or (wanted > current.get("target", 0) and (current.get("pending_units") or current.get("unlinked_orders"))):
        raise WorkflowError("quantity_review", "Check the allocation and resolve pending/unlinked orders before an increase.")
    if any(payload.get(k) != current[k] for k in ("stock_revision", "stock_fingerprint", "allocation_revision")):
        raise WorkflowError("stock_changed", "Stock/allocation changed since review. Check and review again.")
    access = get_access_token(actor=actor)
    inventory = ebay.get_ebay_inventory_adapter()
    a, b = _read_remote(allocation, inventory, access)
    if (a, b) != (current["inventory_available"], current["offer_available"]):
        raise WorkflowError("remote_changed", "eBay quantity changed since it was checked. Check again; nothing sent.")
    try:
        with transaction.atomic(using=using):
            if InventoryItem.objects.using(using).filter(pk=allocation.item_id, stock_revision=current["stock_revision"]).update(stock_revision=F("stock_revision")) != 1:
                raise WorkflowError("stock_changed", "Stock changed before the claim; nothing sent.")
            basis = stock_basis(allocation.item, allocation.environment)
            if basis["fingerprint"] != current["stock_fingerprint"]:
                raise WorkflowError("stock_changed", "Order queue changed before the claim; nothing sent.")
            attempt = EbayQuantityUpdate.objects.using(using).create(allocation=allocation, actor=actor if getattr(actor, "pk", None) else None,
                stock_revision=basis["stock_revision"], allocation_revision=current["allocation_revision"],
                stock_fingerprint=basis["fingerprint"], requested_quantity=wanted, inventory_before=a, offer_before=b)
            if EbayListingAllocation.objects.using(using).filter(pk=allocation.pk, revision=current["allocation_revision"], current_attempt__isnull=True).update(
                current_attempt=attempt.pk, revision=F("revision") + 1, verification_state="pending",
                allocation_quantity=current["target"], allocation_basis={"events": basis["events"]}) != 1:
                raise WorkflowError("already_updating", "Already updating, or the allocation changed; nothing sent.")
    except (IntegrityError, OperationalError):
        raise WorkflowError("already_updating", "Another stock operation won. Reload; do not retry blindly.") from None
    try:
        if stock_basis(allocation.item, allocation.environment)["fingerprint"] != attempt.stock_fingerprint:
            with transaction.atomic(using=using):
                EbayQuantityUpdate.objects.using(using).filter(pk=attempt.pk, outcome="claimed").update(outcome="definite_failure", completed_at=timezone.now())
                EbayListingAllocation.objects.using(using).filter(pk=allocation.pk, current_attempt=attempt.pk).update(current_attempt=None, verification_state="unverified")
            raise WorkflowError("stock_changed", "Stock changed before send. Nothing was sent; check again.")
        sent = EbayQuantityUpdate.objects.using(using).filter(pk=attempt.pk, outcome="claimed", allocation__current_attempt=attempt.pk,
            allocation__closed_at__isnull=True, allocation__channel_listing__ended_at__isnull=True,
            allocation__item__stock_revision=attempt.stock_revision).update(outcome="in_flight", request_sent_at=timezone.now())
        if sent != 1:
            with transaction.atomic(using=using):
                changed = EbayQuantityUpdate.objects.using(using).filter(pk=attempt.pk, outcome="claimed").update(outcome="definite_failure", completed_at=timezone.now())
                if changed:
                    EbayListingAllocation.objects.using(using).filter(pk=allocation.pk, current_attempt=attempt.pk).update(current_attempt=None, verification_state="unverified")
            raise WorkflowError("stock_changed", "Stock, listing or attempt changed at the send barrier. Nothing sent.")
        # Quantity only, at both controls. Never updateOffer with an old draft.
        inventory.update_quantity(access_token=access, sku=allocation.sku, offer_id=allocation.offer_id, quantity=wanted)
        a, b = _read_remote(allocation, inventory, access)
        allocation.refresh_from_db()
        _finish(allocation, attempt, a, b, stock_basis(allocation.item, allocation.environment))
    except Exception as exc:
        if isinstance(exc, WorkflowError) and exc.key == "stock_changed":
            raise
        value = safe_exception(exc, "inventory.quantity")
        with transaction.atomic(using=using):
            EbayQuantityUpdate.objects.using(using).filter(pk=attempt.pk, outcome__in=UNRESOLVED).update(outcome="unknown", diagnostic=value)
            EbayListingAllocation.objects.using(using).filter(pk=allocation.pk, current_attempt=attempt.pk).update(verification_state="unknown")
    return item_quantity_state(allocation.item, allocation.environment)
