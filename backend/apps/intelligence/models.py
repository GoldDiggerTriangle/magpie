from django.db import models

from apps.core.models import TimeStampedUUIDModel


class FieldSuggestion(TimeStampedUUIDModel):
    class Source(models.TextChoices):
        OCR = "ocr", "OCR"
        DUPLICATE = "duplicate", "Duplicate image"
        LATER_AI = "later_ai", "Later AI"

    class ConfidenceBand(models.TextChoices):
        HIGH = "high", "High"
        MEDIUM = "medium", "Medium"
        LOW = "low", "Low"
        CANDIDATE = "candidate", "Candidate"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        EDITED = "edited", "Edited"
        REJECTED = "rejected", "Rejected"

    item = models.ForeignKey(
        "inventory.InventoryItem",
        on_delete=models.CASCADE,
        related_name="field_suggestions",
    )
    photo = models.ForeignKey(
        "photos.PhotoAsset",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="field_suggestions",
    )
    field = models.CharField(max_length=120)
    proposed_value = models.JSONField()
    source = models.CharField(max_length=20, choices=Source.choices)
    confidence_band = models.CharField(max_length=20, choices=ConfidenceBand.choices)
    evidence = models.TextField(blank=True, default="")
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    resolved_value = models.JSONField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["confidence_band", "-created_at"]
        indexes = [
            models.Index(fields=["item", "status"], name="suggestion_item_status_idx"),
            models.Index(fields=["source", "status"], name="suggestion_source_status_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.item.sku} {self.field} {self.source} suggestion"


class ImageFingerprint(TimeStampedUUIDModel):
    photo = models.OneToOneField(
        "photos.PhotoAsset",
        on_delete=models.CASCADE,
        related_name="fingerprint",
    )
    item = models.ForeignKey(
        "inventory.InventoryItem",
        on_delete=models.CASCADE,
        related_name="image_fingerprints",
    )
    perceptual_hash = models.CharField(max_length=16, db_index=True)
    algorithm = models.CharField(max_length=20, default="average_hash_8x8")

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["item"], name="fingerprint_item_idx"),
            models.Index(fields=["perceptual_hash"], name="fingerprint_hash_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.item.sku} {self.algorithm} {self.perceptual_hash}"
