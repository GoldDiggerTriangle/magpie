from django.db import models

from apps.core.models import TimeStampedUUIDModel


class PhotoAsset(TimeStampedUUIDModel):
    class FixupStatus(models.TextChoices):
        NONE = "none", "None"
        PENDING_REVIEW = "pending_review", "Pending review"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

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
    fixup_status = models.CharField(
        max_length=20,
        choices=FixupStatus.choices,
        default=FixupStatus.NONE,
    )
    active_derivative = models.ForeignKey(
        "photos.PhotoDerivative",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

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


class PhotoDerivative(TimeStampedUUIDModel):
    class Status(models.TextChoices):
        PENDING_REVIEW = "pending_review", "Pending review"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    class Source(models.TextChoices):
        LOCAL_FIXUP = "local_fixup", "Local fix-up"
        LOCAL_TWEAK = "local_tweak", "Local tweak"

    photo = models.ForeignKey(
        PhotoAsset,
        on_delete=models.CASCADE,
        related_name="derivatives",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING_REVIEW,
        db_index=True,
    )
    source = models.CharField(
        max_length=20,
        choices=Source.choices,
        default=Source.LOCAL_FIXUP,
    )
    fixed_path = models.CharField(max_length=500)
    thumb_path = models.CharField(max_length=500, blank=True, default="")
    source_path = models.CharField(max_length=500)
    original_processed_path = models.CharField(max_length=500, blank=True, default="")
    original_thumb_path = models.CharField(max_length=500, blank=True, default="")
    width = models.PositiveIntegerField(null=True, blank=True)
    height = models.PositiveIntegerField(null=True, blank=True)
    bytes_fixed = models.PositiveIntegerField(null=True, blank=True)
    pipeline_version = models.CharField(max_length=40, default="sprint17-local-v1")
    operations = models.JSONField(default=list, blank=True)
    parameters = models.JSONField(default=dict, blank=True)
    background_mode = models.CharField(max_length=80, blank=True, default="")
    condition_note = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["photo", "-created_at"]
        indexes = [
            models.Index(fields=["photo", "status"], name="photo_derivative_status_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.photo.item.sku} {self.source} {self.status}"
