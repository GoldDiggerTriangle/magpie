from django.conf import settings
from django.contrib.postgres.indexes import GinIndex
from django.core.exceptions import ValidationError
from django.db import models

from apps.catalog.profiles import get_schema
from apps.core.models import TimeStampedUUIDModel
from apps.core.services.sku import generate_sku


class InventoryItem(TimeStampedUUIDModel):
    class Status(models.TextChoices):
        CAPTURED = "captured", "Captured"
        NEEDS_ID = "needs_identification", "Needs identification"
        NEEDS_CLEANING = "needs_cleaning", "Needs cleaning"
        NEEDS_RESEARCH = "needs_research", "Needs research"
        READY_TO_LIST = "ready_to_list", "Ready to list"
        LISTED = "listed", "Listed"
        SOLD = "sold", "Sold"
        STORED = "stored", "Stored"
        ARCHIVED = "archived", "Archived"
        IN_BULK_LOT = "in_bulk_lot", "Part of bulk lot"

    class Condition(models.TextChoices):
        NEW = "new", "New"
        LIKE_NEW = "like_new", "Like new"
        VERY_GOOD = "very_good", "Very good"
        GOOD = "good", "Good"
        ACCEPTABLE = "acceptable", "Acceptable"
        FOR_PARTS = "for_parts", "For parts / not working"
        UNGRADED = "ungraded", "Ungraded / unknown"

    sku = models.CharField(max_length=40, unique=True, editable=False, db_index=True)
    title = models.CharField(max_length=200, blank=True, default="")
    category = models.ForeignKey(
        "catalog.ProductCategory",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="items",
    )
    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.CAPTURED,
    )
    condition = models.CharField(
        max_length=20,
        choices=Condition.choices,
        default=Condition.UNGRADED,
    )
    location = models.ForeignKey(
        "locations.StorageLocation",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="items",
    )
    acquisition = models.ForeignKey(
        "acquisitions.AcquisitionRecord",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="items",
    )

    acquisition_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )
    estimated_value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )
    min_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )
    target_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )
    currency = models.CharField(max_length=3, default="AUD")

    notes = models.TextField(blank=True, default="")
    attributes = models.JSONField(default=dict, blank=True)

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="items",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"], name="item_status_idx"),
            models.Index(fields=["category"], name="item_category_idx"),
            GinIndex(fields=["attributes"], name="item_attributes_gin"),
        ]

    def clean(self) -> None:
        profile_key = self.category.profile_key if self.category else ""
        try:
            self.attributes = get_schema(profile_key).validate(self.attributes or {})
        except ValueError as exc:
            raise ValidationError({"attributes": str(exc)}) from exc

    def save(self, *args, **kwargs) -> None:
        if not self.sku:
            prefix = (
                self.category.sku_prefix
                if self.category and self.category.sku_prefix
                else "GSP"
            )
            self.sku = generate_sku(prefix)
        super().save(*args, **kwargs)

    @property
    def main_photo(self):
        return self.photos.filter(is_main=True).first() or self.photos.order_by(
            "order_index"
        ).first()

    def __str__(self) -> str:
        return f"{self.sku} - {self.title or 'Untitled'}"
