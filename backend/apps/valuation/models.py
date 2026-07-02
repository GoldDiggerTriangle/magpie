from django.db import models

from apps.core.models import TimeStampedUUIDModel


class Metal(models.TextChoices):
    GOLD = "gold", "Gold"
    SILVER = "silver", "Silver"
    PLATINUM = "platinum", "Platinum"
    PALLADIUM = "palladium", "Palladium"


class FeeSchedule(TimeStampedUUIDModel):
    class SellerMode(models.TextChoices):
        FREE_SELLING = "free_selling", "Free selling"
        PRO_STARTER = "pro_starter", "Pro Starter"
        PRO_OTHER = "pro_other", "Pro Basic or above"
        LEGACY_MANUAL = "legacy_manual", "Legacy / manual"

    name = models.CharField(max_length=120)
    effective_from = models.DateField()
    is_active = models.BooleanField(default=True)
    seller_mode = models.CharField(
        max_length=24,
        choices=SellerMode.choices,
        default=SellerMode.LEGACY_MANUAL,
        db_index=True,
    )
    price_basis = models.CharField(
        max_length=24,
        default="seller_receives",
        help_text="Canonical basis this schedule expects for sale prices.",
    )
    buyer_protection_fee_enabled = models.BooleanField(default=False)
    international_delivery_pct = models.DecimalField(max_digits=6, decimal_places=3, default=0)
    final_value_pct = models.DecimalField(max_digits=6, decimal_places=3)
    per_order_fee = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    promoted_pct = models.DecimalField(max_digits=6, decimal_places=3, default=0)
    gst_pct = models.DecimalField(max_digits=6, decimal_places=3, default=0)
    default_packaging_cost = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    default_outbound_shipping = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    notes = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-effective_from"]

    def __str__(self) -> str:
        return f"{self.name} from {self.effective_from}"


class ValuationReport(TimeStampedUUIDModel):
    class Strategy(models.TextChoices):
        COMP_BASED = "comp_based", "Comparable-based"
        COMMODITY_MANUAL = "commodity_manual", "Commodity (manual inputs)"
        COMMODITY_LIVE = "commodity_live", "Commodity (live spot) - Sprint 3"

    item = models.ForeignKey(
        "inventory.InventoryItem",
        on_delete=models.CASCADE,
        related_name="valuation_reports",
    )
    strategy = models.CharField(
        max_length=20,
        choices=Strategy.choices,
        default=Strategy.COMP_BASED,
    )
    is_current = models.BooleanField(default=False)

    estimate_low = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    estimate_median = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    estimate_high = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    suggested_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    fast_sale_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    patient_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    min_acceptable_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )
    currency = models.CharField(max_length=3, default="AUD")

    confidence_score = models.FloatField(null=True, blank=True)
    confidence_reason = models.TextField(blank=True, default="")

    is_overridden = models.BooleanField(default=False)
    override_reason = models.TextField(blank=True, default="")

    inputs = models.JSONField(default=dict, blank=True)
    fee_schedule = models.ForeignKey(
        "valuation.FeeSchedule",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="valuation_reports",
    )
    notes = models.TextField(blank=True, default="")
    comparables = models.ManyToManyField(
        "research.Comparable",
        through="valuation.ValuationComparable",
        related_name="valuation_reports",
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["item"],
                condition=models.Q(is_current=True),
                name="one_current_valuation_per_item",
            ),
            models.CheckConstraint(
                condition=models.Q(is_overridden=False) | ~models.Q(override_reason=""),
                name="valuation_override_has_reason",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.item} valuation ({self.strategy})"


class ValuationComparable(TimeStampedUUIDModel):
    report = models.ForeignKey(
        "valuation.ValuationReport",
        on_delete=models.CASCADE,
        related_name="comp_links",
    )
    comparable = models.ForeignKey("research.Comparable", on_delete=models.PROTECT)
    included = models.BooleanField(default=True)
    exclude_reason = models.TextField(blank=True, default="")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["report", "comparable"],
                name="uniq_report_comparable",
            ),
            models.CheckConstraint(
                condition=models.Q(included=True) | ~models.Q(exclude_reason=""),
                name="excluded_comparable_has_reason",
            ),
        ]

    def __str__(self) -> str:
        state = "included" if self.included else "excluded"
        return f"{self.comparable} on {self.report_id} ({state})"


class MetalSpotCache(TimeStampedUUIDModel):
    metal = models.CharField(max_length=12, choices=Metal.choices)
    currency = models.CharField(max_length=3, default="AUD")
    provider = models.CharField(max_length=60)
    price_per_gram = models.DecimalField(max_digits=14, decimal_places=6)
    provider_price = models.DecimalField(max_digits=14, decimal_places=6)
    provider_units = models.CharField(max_length=20)
    as_of = models.DateTimeField()
    fetched_at = models.DateTimeField()

    class Meta:
        ordering = ["metal", "currency", "provider"]
        constraints = [
            models.UniqueConstraint(
                fields=["metal", "currency", "provider"],
                name="uniq_metal_currency_provider",
            )
        ]

    def __str__(self) -> str:
        return f"{self.metal} {self.currency} via {self.provider}"
