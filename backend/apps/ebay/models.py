from __future__ import annotations

import secrets
import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import TimeStampedUUIDModel
from apps.ebay.constants import (
    DEFAULT_FAKE_ENVIRONMENT,
    EBAY_ENV_PRODUCTION,
    EBAY_ENV_SANDBOX,
    OAUTH_STATE_TTL_MINUTES,
)
from apps.ebay.fields import EncryptedTextField
from apps.ebay.health_schema import validate_operations


class HealthQuerySet(models.QuerySet):
    def update(self, **kwargs):
        if "operations" in kwargs:
            validate_operations(kwargs["operations"])
        return super().update(**kwargs)

    def bulk_create(self, objs, **kwargs):
        for obj in objs:
            obj.full_clean(validate_unique=False, validate_constraints=False)
        return super().bulk_create(objs, **kwargs)

    def bulk_update(self, objs, fields, **kwargs):
        # Conditional CASE updates bypass model.save; disallow this alternate path.
        from django.core.exceptions import ValidationError
        raise ValidationError("Use validated health conditional updates, not bulk_update.")


class EbayConnectionHealth(TimeStampedUUIDModel):
    environment = models.CharField(max_length=12, choices=[("production", "Production"), ("sandbox", "Sandbox")])
    principal = models.CharField(max_length=12, choices=[("seller", "Seller"), ("application", "Application")])
    connection_id = models.UUIDField(default=uuid.uuid4, editable=False)
    revision = models.PositiveBigIntegerField(default=0)
    operations = models.JSONField(default=dict, blank=True, validators=[validate_operations])
    check_id = models.UUIDField(null=True, blank=True)
    check_started_at = models.DateTimeField(null=True, blank=True)
    check_completed_at = models.DateTimeField(null=True, blank=True)
    next_check_at = models.DateTimeField(null=True, blank=True)
    objects = HealthQuerySet.as_manager()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["environment", "principal"], name="one_connection_health_per_principal")]

    def save(self, *args, **kwargs):
        self.full_clean(validate_unique=False, validate_constraints=False)
        return super().save(*args, **kwargs)


class EbayCredential(TimeStampedUUIDModel):
    class Environment(models.TextChoices):
        SANDBOX = EBAY_ENV_SANDBOX, "Sandbox"
        PRODUCTION = EBAY_ENV_PRODUCTION, "Production"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="ebay_credentials",
    )
    environment = models.CharField(max_length=12, choices=Environment.choices)
    ebay_user_id = models.CharField(max_length=120, blank=True, default="")
    ebay_username = models.CharField(max_length=120, blank=True, default="")
    scopes = models.JSONField(default=list, blank=True)
    refresh_token = EncryptedTextField()
    refresh_token_expires_at = models.DateTimeField(null=True, blank=True)
    access_token = EncryptedTextField(blank=True, default="")
    access_token_expires_at = models.DateTimeField(null=True, blank=True)
    connected_at = models.DateTimeField(auto_now_add=True)
    last_refresh_at = models.DateTimeField(null=True, blank=True)
    last_refresh_error = models.TextField(blank=True, default="")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["environment"],
                name="one_credential_per_environment",
            )
        ]

    def __str__(self) -> str:
        username = self.ebay_username or self.ebay_user_id or "connected"
        return f"{self.environment}: {username}"


class EbayAppToken(TimeStampedUUIDModel):
    environment = models.CharField(
        max_length=12,
        choices=EbayCredential.Environment.choices,
        unique=True,
    )
    access_token = EncryptedTextField()
    expires_at = models.DateTimeField()

    def __str__(self) -> str:
        return f"{self.environment} app token"


class MerchantLocation(TimeStampedUUIDModel):
    environment = models.CharField(
        max_length=12,
        choices=EbayCredential.Environment.choices,
        unique=True,
    )
    merchant_location_key = models.CharField(max_length=36)
    name = models.CharField(max_length=1000)
    country = models.CharField(max_length=2)
    postal_code = models.CharField(max_length=16, blank=True, default="")
    city = models.CharField(max_length=128, blank=True, default="")
    state = models.CharField(max_length=128, blank=True, default="")
    created_on_ebay = models.BooleanField(default=False)
    fetched_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return f"{self.environment}: {self.merchant_location_key}"


def generate_oauth_state() -> str:
    return secrets.token_urlsafe(32)


def oauth_state_expiry():
    return timezone.now() + timedelta(minutes=OAUTH_STATE_TTL_MINUTES)


class OAuthState(TimeStampedUUIDModel):
    state = models.CharField(max_length=64, unique=True, default=generate_oauth_state)
    expires_at = models.DateTimeField(default=oauth_state_expiry)
    consumed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def is_expired(self) -> bool:
        return self.expires_at <= timezone.now()

    @property
    def is_consumed(self) -> bool:
        return self.consumed_at is not None

    def __str__(self) -> str:
        return f"OAuth state {self.id}"


class EbayAccountSnapshot(TimeStampedUUIDModel):
    environment = models.CharField(
        max_length=12,
        choices=EbayCredential.Environment.choices,
    )
    business_policies_opted_in = models.BooleanField(null=True)
    payment_policies = models.JSONField(default=list, blank=True)
    fulfillment_policies = models.JSONField(default=list, blank=True)
    return_policies = models.JSONField(default=list, blank=True)
    fetched_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["environment"],
                name="one_snapshot_per_environment",
            )
        ]

    def __str__(self) -> str:
        return f"{self.environment} account snapshot"


class EbayOrderSyncState(TimeStampedUUIDModel):
    environment = models.CharField(
        max_length=12,
        choices=EbayCredential.Environment.choices,
        unique=True,
    )
    last_synced_at = models.DateTimeField(null=True, blank=True)
    lookback_days = models.PositiveIntegerField(default=2)

    def __str__(self) -> str:
        return f"{self.environment} order sync state"


class EbayOrderStaging(TimeStampedUUIDModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RESOLVED = "resolved", "Resolved"
        DISMISSED = "dismissed", "Dismissed"

    class FeeStatus(models.TextChoices):
        AUTHORITATIVE = "authoritative", "Authoritative"
        ESTIMATED_OR_UNMAPPED = "estimated_or_unmapped", "Estimated or unmapped"

    environment = models.CharField(
        max_length=12,
        choices=EbayCredential.Environment.choices,
        default=DEFAULT_FAKE_ENVIRONMENT,
    )
    ebay_order_id = models.CharField(max_length=80)
    ebay_line_item_id = models.CharField(max_length=120)
    sku = models.CharField(max_length=120, blank=True, default="")
    quantity = models.PositiveIntegerField(default=1)
    line_price = models.DecimalField(max_digits=12, decimal_places=2)
    sale_date = models.DateField()
    actual_fee = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    fee_status = models.CharField(
        max_length=32,
        choices=FeeStatus.choices,
        default=FeeStatus.ESTIMATED_OR_UNMAPPED,
    )
    buyer_region = models.CharField(max_length=80, blank=True, default="")
    raw = models.JSONField(default=dict, blank=True)
    finance_snapshot = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    resolved_sale = models.ForeignKey(
        "sales.SaleRecord",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="staging_sources",
    )
    notes = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-sale_date", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["environment", "ebay_order_id", "ebay_line_item_id"],
                name="uniq_ebay_staging_order_line",
            )
        ]
        indexes = [
            models.Index(fields=["status", "sale_date"]),
            models.Index(fields=["sku"]),
            models.Index(fields=["ebay_order_id", "ebay_line_item_id"]),
        ]

    def __str__(self) -> str:
        return f"{self.ebay_order_id}/{self.ebay_line_item_id} staging"


class EbayOrderDuplicateCandidate(TimeStampedUUIDModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        LINKED = "linked", "Linked"
        DISMISSED = "dismissed", "Dismissed"

    environment = models.CharField(
        max_length=12,
        choices=EbayCredential.Environment.choices,
        default=DEFAULT_FAKE_ENVIRONMENT,
    )
    ebay_order_id = models.CharField(max_length=80)
    ebay_line_item_id = models.CharField(max_length=120)
    sku = models.CharField(max_length=120, blank=True, default="")
    item = models.ForeignKey(
        "inventory.InventoryItem",
        on_delete=models.CASCADE,
        related_name="ebay_duplicate_candidates",
    )
    manual_sale = models.ForeignKey(
        "sales.SaleRecord",
        on_delete=models.CASCADE,
        related_name="ebay_duplicate_candidates",
    )
    quantity = models.PositiveIntegerField(default=1)
    line_price = models.DecimalField(max_digits=12, decimal_places=2)
    sale_date = models.DateField()
    raw = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    notes = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-sale_date", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["environment", "ebay_order_id", "ebay_line_item_id"],
                name="uniq_ebay_duplicate_order_line",
            )
        ]
        indexes = [
            models.Index(fields=["status", "sale_date"]),
            models.Index(fields=["sku"]),
            models.Index(fields=["item"]),
        ]

    def __str__(self) -> str:
        return f"{self.ebay_order_id}/{self.ebay_line_item_id} duplicate candidate"
