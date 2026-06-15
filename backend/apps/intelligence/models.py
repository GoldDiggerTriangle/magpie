from django.db import models

from apps.core.models import TimeStampedUUIDModel
from apps.ebay.fields import EncryptedTextField


class FieldSuggestion(TimeStampedUUIDModel):
    class Source(models.TextChoices):
        OCR = "ocr", "OCR"
        DUPLICATE = "duplicate", "Duplicate image"
        AI = "ai", "AI research"
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


class AICredential(TimeStampedUUIDModel):
    class Provider(models.TextChoices):
        OPENAI = "openai", "OpenAI"

    provider = models.CharField(
        max_length=40,
        choices=Provider.choices,
        unique=True,
        default=Provider.OPENAI,
    )
    model_id = models.CharField(max_length=120, default="gpt-4.1-mini")
    api_key = EncryptedTextField()
    monthly_budget_cap_usd = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default="5.00",
    )
    is_active = models.BooleanField(default=True)
    connected_at = models.DateTimeField(auto_now_add=True)
    last_error = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["provider"]

    def __str__(self) -> str:
        return f"{self.get_provider_display()} {self.model_id}"


class AIResearchCall(TimeStampedUUIDModel):
    class Phase(models.TextChoices):
        IDENTIFY = "identify", "Identify and fill"
        PRICE_ASSIST = "price_assist", "Price assist"

    class Status(models.TextChoices):
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"
        BLOCKED = "blocked", "Blocked"

    item = models.ForeignKey(
        "inventory.InventoryItem",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="ai_research_calls",
    )
    phase = models.CharField(max_length=24, choices=Phase.choices)
    status = models.CharField(max_length=16, choices=Status.choices)
    provider = models.CharField(max_length=40)
    model_id = models.CharField(max_length=120)
    image_count = models.PositiveIntegerField(default=0)
    exif_stripped = models.BooleanField(default=False)
    suggestions_created = models.PositiveIntegerField(default=0)
    search_terms_created = models.PositiveIntegerField(default=0)
    reference_links_created = models.PositiveIntegerField(default=0)
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    estimated_cost_usd = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        default="0.000000",
    )
    request_metadata = models.JSONField(default=dict, blank=True)
    response_metadata = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["phase", "created_at"], name="ai_call_phase_created_idx"),
            models.Index(fields=["provider", "created_at"], name="ai_call_provider_created_idx"),
        ]

    def __str__(self) -> str:
        sku = self.item.sku if self.item_id and self.item else "unknown item"
        return f"{self.phase} {self.status} for {sku}"


class AIResearchSearchTerm(TimeStampedUUIDModel):
    item = models.ForeignKey(
        "inventory.InventoryItem",
        on_delete=models.CASCADE,
        related_name="ai_search_terms",
    )
    phrase = models.CharField(max_length=240)
    source_basis = models.TextField(blank=True, default="")
    created_by_call = models.ForeignKey(
        AIResearchCall,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="search_terms",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["item", "is_active", "created_at"], name="ai_term_item_active_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.item.sku}: {self.phrase}"


class AIReferenceLink(TimeStampedUUIDModel):
    item = models.ForeignKey(
        "inventory.InventoryItem",
        on_delete=models.CASCADE,
        related_name="ai_reference_links",
    )
    label = models.CharField(max_length=160)
    url = models.URLField(max_length=1000)
    source_basis = models.TextField(blank=True, default="")
    created_by_call = models.ForeignKey(
        AIResearchCall,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reference_links",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["item", "created_at"], name="ai_ref_item_created_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.item.sku}: {self.label}"


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
