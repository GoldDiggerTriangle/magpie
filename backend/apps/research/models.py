from django.db import models

from apps.core.models import TimeStampedUUIDModel


class Comparable(TimeStampedUUIDModel):
    class Kind(models.TextChoices):
        ACTIVE = "active", "Active listing"
        SOLD = "sold", "Sold / completed"
        DEALER = "dealer", "Dealer asking"
        CATALOGUE = "catalogue", "Catalogue value"
        MANUAL_ESTIMATE = "manual_estimate", "Manual estimate"
        AUCTION_RESULT = "auction_result", "Auction result"

    class SaleFormat(models.TextChoices):
        UNKNOWN = "unknown", "Unknown"
        AUCTION = "auction", "Auction"
        FIXED_PRICE = "fixed_price", "Fixed price"
        DEALER = "dealer", "Dealer / guide"
        OTHER = "other", "Other"

    class MatchScope(models.TextChoices):
        EXACT = "exact", "Exact item"
        SIMILAR = "similar", "Similar item"

    class PriceBasis(models.TextChoices):
        BUYER_VISIBLE = "buyer_visible", "Buyer-visible total"
        SELLER_RECEIVES = "seller_receives", "Seller receives"
        UNKNOWN = "unknown", "Unknown / review"

    item = models.ForeignKey(
        "inventory.InventoryItem",
        on_delete=models.CASCADE,
        related_name="comparables",
        null=True,
        blank=True,
    )
    descriptor_category = models.ForeignKey(
        "catalog.ProductCategory",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="descriptor_comparables",
    )
    descriptor_terms = models.JSONField(default=list, blank=True)
    descriptor_attributes = models.JSONField(default=dict, blank=True)
    kind = models.CharField(max_length=20, choices=Kind.choices)
    source = models.CharField(max_length=200, blank=True, default="")
    title = models.CharField(max_length=300, blank=True, default="")
    price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    price_basis = models.CharField(
        max_length=24,
        choices=PriceBasis.choices,
        default=PriceBasis.UNKNOWN,
        db_index=True,
    )
    shipping = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, default="AUD")
    condition = models.CharField(max_length=20, blank=True, default="")
    grade = models.CharField(max_length=80, blank=True, default="")
    sale_format = models.CharField(
        max_length=20,
        choices=SaleFormat.choices,
        default=SaleFormat.UNKNOWN,
    )
    source_tag = models.CharField(max_length=80, blank=True, default="", db_index=True)
    match_scope = models.CharField(
        max_length=20,
        choices=MatchScope.choices,
        default=MatchScope.SIMILAR,
    )
    match_reason = models.CharField(max_length=240, blank=True, default="")
    url = models.URLField(blank=True, default="")
    observed_on = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-observed_on", "-created_at"]
        indexes = [
            models.Index(fields=["item"]),
            models.Index(fields=["kind"]),
            models.Index(fields=["source_tag"]),
            models.Index(fields=["sale_format"]),
            models.Index(fields=["match_scope"]),
            models.Index(fields=["descriptor_category"]),
        ]

    def __str__(self) -> str:
        return self.title or f"{self.get_kind_display()} comparable"


class ResearchRecord(TimeStampedUUIDModel):
    item = models.ForeignKey(
        "inventory.InventoryItem",
        on_delete=models.CASCADE,
        related_name="research_records",
    )
    source = models.CharField(max_length=200, blank=True, default="")
    content = models.TextField(blank=True, default="")
    links = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.source or f"Research record {self.id}"

