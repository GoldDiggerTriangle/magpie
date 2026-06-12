from __future__ import annotations

import secrets
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import TimeStampedUUIDModel
from apps.ebay.constants import (
    EBAY_ENV_PRODUCTION,
    EBAY_ENV_SANDBOX,
    OAUTH_STATE_TTL_MINUTES,
)
from apps.ebay.fields import EncryptedTextField


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
