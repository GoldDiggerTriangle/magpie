from django.db import models

from apps.core.models import TimeStampedUUIDModel


class ListingBoilerplate(TimeStampedUUIDModel):
    channel = models.CharField(max_length=30, default="ebay_au")
    name = models.CharField(max_length=120)
    is_active = models.BooleanField(default=True)
    body_html = models.TextField(blank=True, default="")
    notes = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["channel", "name"]

    def __str__(self) -> str:
        state = "active" if self.is_active else "inactive"
        return f"{self.channel}: {self.name} ({state})"


class ListingDraft(TimeStampedUUIDModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        READY = "ready", "Ready"
        EXPORTED = "exported", "Exported"
        STAGED = "staged", "Staged"
        PUBLISHED = "published", "Published"
        PUBLISH_FAILED = "publish_failed", "Publish failed"

    class Format(models.TextChoices):
        FIXED = "fixed", "Fixed price"
        AUCTION = "auction", "Auction"

    item = models.ForeignKey(
        "inventory.InventoryItem",
        on_delete=models.CASCADE,
        related_name="listing_drafts",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    channel = models.CharField(max_length=30, default="ebay_au")
    channel_data = models.JSONField(default=dict, blank=True)

    title = models.CharField(max_length=200, blank=True, default="")
    subtitle = models.CharField(max_length=200, blank=True, default="")
    description_html = models.TextField(blank=True, default="")
    listing_format = models.CharField(
        max_length=10,
        choices=Format.choices,
        default=Format.FIXED,
    )
    price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, default="AUD")
    quantity = models.PositiveIntegerField(default=1)
    est_shipping_note = models.CharField(max_length=200, blank=True, default="")
    item_specifics = models.JSONField(default=list, blank=True)
    photo_ids = models.JSONField(default=list, blank=True)
    include_sku_footer = models.BooleanField(default=False)
    boilerplate = models.ForeignKey(
        "listing.ListingBoilerplate",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="drafts",
    )

    title_edited = models.BooleanField(default=False)
    description_edited = models.BooleanField(default=False)
    generated_meta = models.JSONField(default=dict, blank=True)
    exported_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["item"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self) -> str:
        return f"{self.item.sku} listing draft ({self.status})"
