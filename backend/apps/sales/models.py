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
    def net_proceeds(self) -> Decimal:
        return money(self.sale_price - self.actual_fees_total - self.actual_shipping_cost)

    @property
    def allocated_cost_basis(self) -> Decimal | None:
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
        allocated_cost = self.allocated_cost_basis
        if allocated_cost is None:
            return None
        return money(self.net_proceeds - allocated_cost)

    @property
    def is_superseded(self) -> bool:
        if self.pk is None:
            return False
        return self.corrections.exists()

    def __str__(self) -> str:
        sku = self.item.sku if self.item_id and self.item else "external"
        return f"{sku} sale {self.quantity} on {self.sale_date}"
