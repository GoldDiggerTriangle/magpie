from django.db import models

from apps.core.models import TimeStampedUUIDModel


class PhotoAsset(TimeStampedUUIDModel):
    class Role(models.TextChoices):
        MAIN = "main", "Main"
        FRONT = "front", "Front"
        BACK = "back", "Back"
        DETAIL = "detail", "Detail / close-up"
        BEFORE = "before", "Before"
        AFTER = "after", "After"
        OTHER = "other", "Other"

    item = models.ForeignKey(
        "inventory.InventoryItem",
        on_delete=models.CASCADE,
        related_name="photos",
    )
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.OTHER)
    is_main = models.BooleanField(default=False)
    order_index = models.PositiveIntegerField(default=0)

    original_path = models.CharField(max_length=500)
    processed_path = models.CharField(max_length=500, blank=True, default="")
    thumb_path = models.CharField(max_length=500, blank=True, default="")

    width = models.PositiveIntegerField(null=True, blank=True)
    height = models.PositiveIntegerField(null=True, blank=True)
    bytes_original = models.PositiveIntegerField(null=True, blank=True)
    exif_stripped = models.BooleanField(default=False)
    quality_score = models.FloatField(null=True, blank=True)

    class Meta:
        ordering = ["item", "order_index", "created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["item"],
                condition=models.Q(is_main=True),
                name="one_main_photo_per_item",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.item.sku} {self.role} photo"
