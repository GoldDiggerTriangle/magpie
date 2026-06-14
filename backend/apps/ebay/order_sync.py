from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import serializers

import integrations.ebay as ebay_integration
from apps.audit.services import record
from apps.ebay.constants import (
    AUDIT_ORDER_DUPLICATE_FLAGGED,
    AUDIT_ORDER_STAGING_RESOLVED,
    AUDIT_ORDER_SYNC_COMPLETED,
    AUDIT_ORDER_SYNC_FAILED,
    AUDIT_ORDER_SYNC_STARTED,
)
from apps.ebay.models import (
    EbayCredential,
    EbayOrderDuplicateCandidate,
    EbayOrderStaging,
    EbayOrderSyncState,
)
from apps.ebay.services import get_access_token
from apps.inventory.models import InventoryItem
from apps.listing.models import ListingDraft
from apps.sales.models import SaleRecord, money
from apps.sales.services import create_sale_record

DEFAULT_FIRST_SYNC_DAYS = 90


@dataclass(frozen=True)
class OrderLine:
    order_id: str
    line_item_id: str
    sku: str
    quantity: int
    line_price: Decimal
    sale_date: date
    buyer_region: str
    raw: dict


@dataclass(frozen=True)
class FeeMapping:
    amount: Decimal | None
    status: str
    transaction_id: str
    breakdown: dict
    snapshot: dict


def sync_orders(
    *,
    actor=None,
    first_sync_days: int = DEFAULT_FIRST_SYNC_DAYS,
    lookback_days: int | None = None,
) -> dict:
    environment = ebay_integration.effective_environment()
    state, _created = EbayOrderSyncState.objects.get_or_create(environment=environment)
    end = timezone.now()
    overlap_days = int(lookback_days if lookback_days is not None else state.lookback_days)
    if state.last_synced_at:
        start = state.last_synced_at - timedelta(days=overlap_days)
    else:
        start = end - timedelta(days=first_sync_days)

    counts = {
        "created": 0,
        "staged": 0,
        "duplicate_flagged": 0,
        "skipped": 0,
        "fee_authoritative": 0,
        "fee_estimated_or_unmapped": 0,
    }
    record(
        actor=actor,
        action=AUDIT_ORDER_SYNC_STARTED,
        target_type="ebay_order_sync",
        payload={"environment": environment, "start": start.isoformat(), "end": end.isoformat()},
    )
    try:
        credential = EbayCredential.objects.filter(environment=environment).first()
        if credential is None:
            raise ebay_integration.EbayUnavailable("eBay account is not connected.")
        missing_scopes = sorted(set(_order_sync_scopes()) - set(credential.scopes or []))
        if missing_scopes:
            raise ebay_integration.EbayUnavailable(
                "eBay re-consent is required before syncing orders."
            )
        access_token = get_access_token(actor=actor)
        orders = ebay_integration.get_ebay_order_adapter().list_orders(
            access_token=access_token,
            start=start,
            end=end,
        )
        transactions = ebay_integration.get_ebay_finances_adapter().list_transactions(
            access_token=access_token,
            start=start,
            end=end,
        )
        for order in orders:
            order_lines = normalize_order(order)
            for line in order_lines:
                if _has_order_line(environment, line):
                    counts["skipped"] += 1
                    continue
                fee = map_fee_for_line(
                    line=line,
                    order_line_count=len(order_lines),
                    transactions=transactions,
                )
                counts[
                    "fee_authoritative"
                    if fee.status == SaleRecord.FeeStatus.AUTHORITATIVE
                    else "fee_estimated_or_unmapped"
                ] += 1
                result = _import_line(environment=environment, line=line, fee=fee, actor=actor)
                counts[result] += 1
        state.last_synced_at = end
        state.lookback_days = overlap_days
        state.save(update_fields=["last_synced_at", "lookback_days", "updated_at"])
    except Exception as exc:
        record(
            actor=actor,
            action=AUDIT_ORDER_SYNC_FAILED,
            target_type="ebay_order_sync",
            payload={"environment": environment, "reason": _safe_error(exc)},
        )
        raise

    payload = {
        "environment": environment,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "counts": counts,
    }
    record(
        actor=actor,
        action=AUDIT_ORDER_SYNC_COMPLETED,
        target_type="ebay_order_sync",
        payload=payload,
    )
    return payload


def normalize_order(order: dict) -> list[OrderLine]:
    order_id = str(order.get("orderId") or order.get("order_id") or "")
    order_date = _date_from_value(
        order.get("creationDate") or order.get("creation_date") or order.get("saleDate")
    )
    buyer_region = _buyer_region(order)
    lines = order.get("lineItems") or order.get("line_items") or []
    if not order_id or not isinstance(lines, list):
        return []
    normalized: list[OrderLine] = []
    for index, raw_line in enumerate(lines, start=1):
        if not isinstance(raw_line, dict):
            continue
        line_id = str(
            raw_line.get("lineItemId")
            or raw_line.get("line_item_id")
            or raw_line.get("legacyItemId")
            or raw_line.get("legacy_item_id")
            or index
        )
        quantity = int(raw_line.get("quantity") or raw_line.get("quantityPurchased") or 1)
        line_price = _money_from(
            raw_line.get("lineItemCost")
            or raw_line.get("discountedLineItemCost")
            or raw_line.get("line_price")
            or raw_line.get("price")
            or {}
        )
        if line_price == Decimal("0.00") and raw_line.get("unitPrice"):
            line_price = money(_money_from(raw_line["unitPrice"]) * Decimal(quantity))
        normalized.append(
            OrderLine(
                order_id=order_id,
                line_item_id=line_id,
                sku=str(raw_line.get("sku") or raw_line.get("sellerSku") or "").strip(),
                quantity=quantity,
                line_price=line_price,
                sale_date=order_date,
                buyer_region=buyer_region,
                raw={"order": order, "line": raw_line},
            )
        )
    return normalized


def map_fee_for_line(
    *,
    line: OrderLine,
    order_line_count: int,
    transactions: list[dict],
) -> FeeMapping:
    order_transactions = [
        transaction
        for transaction in transactions
        if _transaction_order_id(transaction) == line.order_id
    ]
    candidates = [
        transaction
        for transaction in order_transactions
        if line.line_item_id in _transaction_line_ids(transaction)
    ]
    if not candidates and order_line_count == 1 and len(order_transactions) == 1:
        candidates = order_transactions

    if len(candidates) != 1:
        return FeeMapping(
            amount=None,
            status=SaleRecord.FeeStatus.ESTIMATED_OR_UNMAPPED,
            transaction_id="",
            breakdown={},
            snapshot={
                "join_status": "unmapped",
                "transactions": order_transactions,
            },
        )

    transaction_row = candidates[0]
    fee_amount, breakdown = _fee_amount_from_transaction(transaction_row)
    if fee_amount is None:
        status = SaleRecord.FeeStatus.ESTIMATED_OR_UNMAPPED
    else:
        status = SaleRecord.FeeStatus.AUTHORITATIVE
    return FeeMapping(
        amount=fee_amount,
        status=status,
        transaction_id=str(
            transaction_row.get("transactionId") or transaction_row.get("transaction_id") or ""
        ),
        breakdown=breakdown,
        snapshot={
            "join_status": "line_match" if status == SaleRecord.FeeStatus.AUTHORITATIVE else "fee_unmapped",
            "transaction": transaction_row,
        },
    )


@transaction.atomic
def resolve_staging(
    staging: EbayOrderStaging,
    *,
    action: str,
    actor=None,
    item: InventoryItem | None = None,
    item_data: dict | None = None,
    cost_basis_override=None,
    notes: str = "",
) -> SaleRecord:
    staging = EbayOrderStaging.objects.select_for_update().get(pk=staging.pk)
    if staging.status != EbayOrderStaging.Status.PENDING:
        raise serializers.ValidationError({"status": ["This staging row is already resolved."]})

    if action == "link":
        if item is None:
            raise serializers.ValidationError({"item": ["Select an item to link."]})
        item = InventoryItem.objects.get(pk=item.pk)
        sale = _sale_from_staging(staging, item=item, cost_basis_override=cost_basis_override, notes=notes)
    elif action == "quick_create":
        payload = item_data or {}
        item = InventoryItem.objects.create(
            title=str(payload.get("title") or staging.raw.get("line", {}).get("title") or staging.sku or "eBay sale"),
            category=payload.get("category"),
            quantity_total=max(int(payload.get("quantity_total") or staging.quantity), staging.quantity),
            acquisition_cost=payload.get("acquisition_cost"),
            estimated_value=payload.get("estimated_value"),
            notes=str(payload.get("notes") or ""),
        )
        sale = _sale_from_staging(staging, item=item, cost_basis_override=cost_basis_override, notes=notes)
    elif action == "mark_external":
        sale = _sale_from_staging(
            staging,
            item=None,
            cost_basis_override=cost_basis_override,
            notes=notes,
            is_external=True,
        )
    else:
        raise serializers.ValidationError({"action": ["Unsupported staging resolution."]})

    staging.status = EbayOrderStaging.Status.RESOLVED
    staging.resolved_sale = sale
    staging.notes = notes or staging.notes
    staging.save(update_fields=["status", "resolved_sale", "notes", "updated_at"])
    record(
        actor=actor,
        action=AUDIT_ORDER_STAGING_RESOLVED,
        target_type="ebay_order_staging",
        target_id=staging.id,
        payload={
            "environment": staging.environment,
            "action": action,
            "sale_id": str(sale.id),
            "order_id": staging.ebay_order_id,
            "line_item_id": staging.ebay_line_item_id,
        },
    )
    return sale


@transaction.atomic
def resolve_duplicate_candidate(
    candidate: EbayOrderDuplicateCandidate,
    *,
    action: str,
    actor=None,
) -> EbayOrderDuplicateCandidate:
    candidate = EbayOrderDuplicateCandidate.objects.select_for_update().get(pk=candidate.pk)
    if candidate.status != EbayOrderDuplicateCandidate.Status.PENDING:
        return candidate
    if action == "link":
        sale = candidate.manual_sale
        sale.ebay_order_id = candidate.ebay_order_id
        sale.ebay_line_item_id = candidate.ebay_line_item_id
        sale.channel_data = {
            **(sale.channel_data or {}),
            "ebay_duplicate_candidate_id": str(candidate.id),
            "ebay_duplicate_linked_at": timezone.now().isoformat(),
        }
        sale.save(update_fields=["ebay_order_id", "ebay_line_item_id", "channel_data", "updated_at"])
        candidate.status = EbayOrderDuplicateCandidate.Status.LINKED
    elif action == "dismiss":
        candidate.status = EbayOrderDuplicateCandidate.Status.DISMISSED
    else:
        raise serializers.ValidationError({"action": ["Unsupported duplicate resolution."]})
    candidate.save(update_fields=["status", "updated_at"])
    return candidate


def _import_line(*, environment: str, line: OrderLine, fee: FeeMapping, actor=None) -> str:
    item = InventoryItem.objects.filter(sku=line.sku).first() if line.sku else None
    if item is None:
        _stage_line(environment=environment, line=line, fee=fee)
        return "staged"

    duplicate = _duplicate_manual_sale(item=item, line=line)
    if duplicate is not None:
        _flag_duplicate(environment=environment, line=line, item=item, duplicate=duplicate, actor=actor)
        return "duplicate_flagged"

    sale = create_sale_record(
        data=_sale_data_for_line(line=line, fee=fee, item=item)
    )
    _mark_local_listing_synced(sale)
    return "created"


def _sale_from_staging(
    staging: EbayOrderStaging,
    *,
    item: InventoryItem | None,
    cost_basis_override,
    notes: str,
    is_external: bool = False,
) -> SaleRecord:
    fee = FeeMapping(
        amount=staging.actual_fee if staging.fee_status == SaleRecord.FeeStatus.AUTHORITATIVE else None,
        status=staging.fee_status,
        transaction_id="",
        breakdown={},
        snapshot=staging.finance_snapshot,
    )
    line = OrderLine(
        order_id=staging.ebay_order_id,
        line_item_id=staging.ebay_line_item_id,
        sku=staging.sku,
        quantity=staging.quantity,
        line_price=staging.line_price,
        sale_date=staging.sale_date,
        buyer_region=staging.buyer_region,
        raw=staging.raw,
    )
    data = _sale_data_for_line(line=line, fee=fee, item=item)
    data["notes"] = notes
    data["cost_basis_override"] = cost_basis_override
    data["is_external"] = is_external
    data["cost_basis_unknown"] = bool(is_external and cost_basis_override in {None, ""})
    return create_sale_record(data=data)


def _sale_data_for_line(
    *,
    line: OrderLine,
    fee: FeeMapping,
    item: InventoryItem | None,
) -> dict:
    return {
        "item": item,
        "sale_date": line.sale_date,
        "quantity": line.quantity,
        "sale_price": line.line_price,
        "channel": SaleRecord.Channel.EBAY_AU,
        "actual_fees_total": fee.amount,
        "actual_fee_breakdown": fee.breakdown,
        "fee_status": fee.status,
        "actual_shipping_cost": Decimal("0.00"),
        "provenance": SaleRecord.Provenance.EBAY_SYNC,
        "ebay_order_id": line.order_id,
        "ebay_line_item_id": line.line_item_id,
        "ebay_transaction_id": fee.transaction_id,
        "channel_data": {
            "ebay_raw": line.raw,
            "ebay_finance_snapshot": fee.snapshot,
        },
    }


def _stage_line(*, environment: str, line: OrderLine, fee: FeeMapping) -> EbayOrderStaging:
    try:
        staging, _created = EbayOrderStaging.objects.get_or_create(
            environment=environment,
            ebay_order_id=line.order_id,
            ebay_line_item_id=line.line_item_id,
            defaults={
                "sku": line.sku,
                "quantity": line.quantity,
                "line_price": line.line_price,
                "sale_date": line.sale_date,
                "actual_fee": fee.amount,
                "fee_status": fee.status,
                "buyer_region": line.buyer_region,
                "raw": line.raw,
                "finance_snapshot": fee.snapshot,
            },
        )
    except IntegrityError:
        staging = EbayOrderStaging.objects.get(
            environment=environment,
            ebay_order_id=line.order_id,
            ebay_line_item_id=line.line_item_id,
        )
    return staging


def _flag_duplicate(
    *,
    environment: str,
    line: OrderLine,
    item: InventoryItem,
    duplicate: SaleRecord,
    actor=None,
) -> None:
    candidate, created = EbayOrderDuplicateCandidate.objects.get_or_create(
        environment=environment,
        ebay_order_id=line.order_id,
        ebay_line_item_id=line.line_item_id,
        defaults={
            "sku": line.sku,
            "item": item,
            "manual_sale": duplicate,
            "quantity": line.quantity,
            "line_price": line.line_price,
            "sale_date": line.sale_date,
            "raw": line.raw,
        },
    )
    if created:
        record(
            actor=actor,
            action=AUDIT_ORDER_DUPLICATE_FLAGGED,
            target_type="ebay_order_duplicate_candidate",
            target_id=candidate.id,
            payload={
                "environment": environment,
                "order_id": line.order_id,
                "line_item_id": line.line_item_id,
                "item_id": str(item.id),
                "manual_sale_id": str(duplicate.id),
            },
        )


def _has_order_line(environment: str, line: OrderLine) -> bool:
    lookup = {
        "ebay_order_id": line.order_id,
        "ebay_line_item_id": line.line_item_id,
    }
    return (
        SaleRecord.objects.filter(**lookup).exists()
        or EbayOrderStaging.objects.filter(environment=environment, **lookup).exists()
        or EbayOrderDuplicateCandidate.objects.filter(environment=environment, **lookup).exists()
    )


def _duplicate_manual_sale(*, item: InventoryItem, line: OrderLine) -> SaleRecord | None:
    low = line.sale_date - timedelta(days=2)
    high = line.sale_date + timedelta(days=2)
    for sale in (
        SaleRecord.objects.filter(
            item=item,
            provenance=SaleRecord.Provenance.MANUAL,
            quantity=line.quantity,
            sale_date__range=(low, high),
        )
        .active()
        .order_by("-sale_date")
    ):
        if abs(money(sale.sale_price) - money(line.line_price)) <= Decimal("1.00"):
            return sale
    return None


def _mark_local_listing_synced(sale: SaleRecord) -> None:
    if not sale.item_id:
        return
    draft = (
        ListingDraft.objects.filter(item_id=sale.item_id, channel=SaleRecord.Channel.EBAY_AU)
        .order_by("-created_at")
        .first()
    )
    if draft is None:
        return
    channel_data = dict(draft.channel_data or {})
    channel_data.update(
        {
            "last_ebay_order_id": sale.ebay_order_id,
            "last_ebay_line_item_id": sale.ebay_line_item_id,
            "last_ebay_sale_synced_at": timezone.now().isoformat(),
        }
    )
    draft.channel_data = channel_data
    draft.save(update_fields=["channel_data", "updated_at"])


def _date_from_value(value) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    text = str(value or "")
    if not text:
        return timezone.now().date()
    normalized = text.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized).date()
    except ValueError:
        return timezone.now().date()


def _money_from(value) -> Decimal:
    if isinstance(value, dict):
        value = value.get("value") or value.get("amount") or "0"
    return money(value)


def _buyer_region(order: dict) -> str:
    buyer = order.get("buyer") if isinstance(order.get("buyer"), dict) else {}
    address = buyer.get("taxAddress") or buyer.get("buyerRegistrationAddress") or {}
    if not isinstance(address, dict):
        return ""
    return str(address.get("stateOrProvince") or address.get("countryCode") or "")


def _transaction_order_id(transaction: dict) -> str:
    references = transaction.get("references") if isinstance(transaction.get("references"), list) else []
    for reference in references:
        if not isinstance(reference, dict):
            continue
        reference_type = str(reference.get("referenceType") or "").upper()
        if reference_type in {"ORDER_ID", "ORDER"} and reference.get("referenceId"):
            return str(reference["referenceId"])
    return str(transaction.get("orderId") or transaction.get("order_id") or "")


def _transaction_line_ids(transaction: dict) -> set[str]:
    line_ids = set()
    for key in ["lineItemId", "line_item_id", "orderLineItemId", "order_line_item_id"]:
        if transaction.get(key):
            line_ids.add(str(transaction[key]))
    lines = transaction.get("orderLineItems") or transaction.get("order_line_items") or []
    if isinstance(lines, list):
        for row in lines:
            if not isinstance(row, dict):
                continue
            for key in ["lineItemId", "line_item_id", "orderLineItemId", "order_line_item_id"]:
                if row.get(key):
                    line_ids.add(str(row[key]))
    return line_ids


def _fee_amount_from_transaction(transaction: dict) -> tuple[Decimal | None, dict]:
    fee_rows = transaction.get("fees") or transaction.get("feeBreakdown") or []
    if isinstance(fee_rows, list) and fee_rows:
        breakdown = {}
        total = Decimal("0.00")
        for index, fee in enumerate(fee_rows, start=1):
            if not isinstance(fee, dict):
                continue
            name = str(fee.get("type") or fee.get("feeType") or f"fee_{index}")
            amount = _money_from(fee.get("amount") or fee.get("feeAmount") or fee)
            total += abs(amount)
            breakdown[name] = str(abs(amount))
        return money(total), breakdown

    for key in ["totalFeeAmount", "feeAmount", "finalValueFee"]:
        if transaction.get(key):
            amount = abs(_money_from(transaction[key]))
            return money(amount), {key: str(amount)}
    return None, {}


def _safe_error(exc: Exception) -> str:
    text = str(exc) or exc.__class__.__name__
    for blocked in ["access_token", "refresh_token", "authorization_code", "token", "code"]:
        text = text.replace(blocked, "credential")
    return text[:300]


def _order_sync_scopes() -> list[str]:
    from apps.ebay.constants import EBAY_SCOPES

    return [
        scope
        for scope in EBAY_SCOPES
        if scope.endswith("/sell.fulfillment.readonly") or scope.endswith("/sell.finances")
    ]
