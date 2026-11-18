from decimal import Decimal, ROUND_HALF_UP

from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.db.models import Exists, OuterRef

from apps.core.models import TimeStampedUUIDModel


CENT = Decimal("0.01")


def money(value) -> Decimal:
    return Decimal(str(value or "0")).quantize(CENT, rounding=ROUND_HALF_UP)


class SaleRecordQuerySet(models.QuerySet):
    def active(self):
        corrections = self.model.objects.filter(corrected_from=OuterRef("pk"))
        return self.annotate(_has_correction=Exists(corrections)).filter(
            _has_correction=False
        )


class SaleRecord(TimeStampedUUIDModel):
    class Channel(models.TextChoices):
        EBAY_AU = "ebay_au", "eBay AU"
        MANUAL = "manual", "Manual"
        OTHER = "other", "Other"

    class Provenance(models.TextChoices):
        MANUAL = "manual", "Manual"
        EBAY_SYNC = "ebay_sync", "eBay sync"

    class FeeStatus(models.TextChoices):
        AUTHORITATIVE = "authoritative", "Authoritative"
        ESTIMATED_OR_UNMAPPED = "estimated_or_unmapped", "Estimated or unmapped"

    item = models.ForeignKey(
        "inventory.InventoryItem",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sales",
    )
    is_external = models.BooleanField(default=False)
    cost_basis_unknown = models.BooleanField(default=False)
    sale_date = models.DateField()
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    sale_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    channel = models.CharField(
        max_length=20,
        choices=Channel.choices,
        default=Channel.MANUAL,
    )
    actual_fees_total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    actual_fee_breakdown = models.JSONField(default=dict, blank=True)
    fee_status = models.CharField(
        max_length=32,
        choices=FeeStatus.choices,
        default=FeeStatus.AUTHORITATIVE,
    )
    actual_shipping_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    cost_basis_override = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    listing_draft = models.ForeignKey(
        "listing.ListingDraft",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sales",
    )
    valuation_snapshot = models.JSONField(default=dict, blank=True)
    estimated_fee_snapshot = models.JSONField(default=dict, blank=True)
    provenance = models.CharField(
        max_length=20,
        choices=Provenance.choices,
        default=Provenance.MANUAL,
    )
    ebay_order_id = models.CharField(max_length=80, blank=True, default="", db_index=True)
    ebay_line_item_id = models.CharField(max_length=120, blank=True, default="", db_index=True)
    ebay_transaction_id = models.CharField(max_length=120, blank=True, default="")
    channel_data = models.JSONField(default=dict, blank=True)
    corrected_from = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="corrections",
    )
    notes = models.TextField(blank=True, default="")

    objects = SaleRecordQuerySet.as_manager()

    def save(self, *args, **kwargs):
        from django.db import transaction
        from django.db.models import F
        from apps.inventory.models import InventoryItem
        using = kwargs.get("using") or self._state.db or "default"
        with transaction.atomic(using=using):
            # An actual write fence also serializes stock changes on SQLite.
            if self.item_id:
                InventoryItem.objects.using(using).filter(pk=self.item_id).update(stock_revision=F("stock_revision") + 1)
            return super().save(*args, **kwargs)

    class Meta:
        ordering = ["-sale_date", "-created_at"]
        indexes = [
            models.Index(fields=["item", "sale_date"]),
            models.Index(fields=["channel"]),
            models.Index(fields=["provenance"]),
            models.Index(fields=["corrected_from"]),
            models.Index(fields=["ebay_order_id", "ebay_line_item_id"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["ebay_order_id", "ebay_line_item_id"],
                condition=(
                    ~Q(ebay_order_id="")
                    & ~Q(ebay_line_item_id="")
                    & Q(corrected_from__isnull=True)
                ),
                name="uniq_active_ebay_order_line_sale",
            ),
        ]

    @property
    def recorded_revenue(self) -> Decimal:
        from apps.valuation.fee_engine import snapshot_for, effective_result
        snapshot = snapshot_for(self)
        return Decimal(effective_result(snapshot)["revenue"]) if snapshot else money(self.sale_price)

    @property
    def effective_fees_total(self) -> Decimal | None:
        from apps.valuation.fee_engine import snapshot_for, effective_result
        snapshot = snapshot_for(self)
        if snapshot:
            value = effective_result(snapshot).get("fees")
            return Decimal(value) if value is not None else None
        return money(self.actual_fees_total) if self.fee_status == self.FeeStatus.AUTHORITATIVE else None

    @property
    def net_proceeds(self) -> Decimal | None:
        from apps.valuation.fee_engine import snapshot_for, effective_result
        frozen = snapshot_for(self)
        if frozen:
            r = effective_result(frozen)
            return money(Decimal(r["revenue"]) - Decimal(r["fees"]) - Decimal(r["cost_components"].get("postage_label", "0"))) if r.get("fees") is not None else None
        if self.fee_status != self.FeeStatus.AUTHORITATIVE:
            return None
        return money(self.sale_price - self.actual_fees_total - self.actual_shipping_cost)

    @property
    def allocated_cost_basis(self) -> Decimal | None:
        from apps.valuation.fee_engine import snapshot_for
        frozen = snapshot_for(self)
        if frozen:
            return Decimal(frozen.result["cost_components"]["acquisition"]) if frozen.result["cost_state"] == "known" else None
        if self.cost_basis_unknown:
            return None
        if self.cost_basis_override is not None:
            return money(self.cost_basis_override)
        if not self.item_id or not self.item or not self.item.acquisition_cost:
            return money(0)
        cost_per_unit = Decimal(self.item.acquisition_cost) / Decimal(self.item.quantity_total)
        return money(cost_per_unit * Decimal(self.quantity))

    @property
    def realised_profit(self) -> Decimal | None:
        from apps.valuation.fee_engine import snapshot_for, effective_result
        frozen = snapshot_for(self)
        if frozen:
            value = effective_result(frozen).get("realised_profit")
            return Decimal(value) if value is not None else None
        allocated_cost = self.allocated_cost_basis
        if allocated_cost is None or self.net_proceeds is None:
            return None
        from apps.profit.ledger import cost_components_for_sale
        costs, state, _ = cost_components_for_sale(self)
        return money(self.recorded_revenue - self.effective_fees_total - sum(costs.values())) if state == "known" else None

    @property
    def is_superseded(self) -> bool:
        if self.pk is None:
            return False
        return self.corrections.exists()

    def __str__(self) -> str:
        sku = self.item.sku if self.item_id and self.item else "external"
        return f"{sku} sale {self.quantity} on {self.sale_date}"
