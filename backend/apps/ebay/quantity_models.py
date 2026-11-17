"""Operational stock records; immutable published drafts are never updated."""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.core.models import TimeStampedUUIDModel
from apps.ebay.diagnostics import validate_diagnostic


class EbayListingAllocation(TimeStampedUUIDModel):
    item = models.ForeignKey("inventory.InventoryItem", on_delete=models.PROTECT, related_name="ebay_allocations")
    draft = models.ForeignKey("listing.ListingDraft", on_delete=models.PROTECT, related_name="stock_allocations")
    channel_listing = models.ForeignKey("listing.ChannelListing", null=True, blank=True, on_delete=models.PROTECT, related_name="stock_allocations")
    environment = models.CharField(max_length=12)
    marketplace = models.CharField(max_length=20, default="EBAY_AU")
    sku = models.CharField(max_length=120)
    offer_id = models.CharField(max_length=100, blank=True, default="")
    listing_id = models.CharField(max_length=100, blank=True, default="")
    allocation_quantity = models.PositiveIntegerField()
    allocation_basis = models.JSONField(default=dict)
    revision = models.PositiveBigIntegerField(default=0)
    verification_state = models.CharField(max_length=24, default="unverified")
    last_inventory_available = models.PositiveIntegerField(null=True, blank=True)
    last_offer_available = models.PositiveIntegerField(null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    current_attempt = models.UUIDField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["item", "environment", "marketplace"], condition=models.Q(closed_at__isnull=True), name="one_open_ebay_allocation"),
            models.UniqueConstraint(fields=["draft", "environment", "marketplace"], name="one_ebay_draft_allocation"),
            models.UniqueConstraint(fields=["environment", "marketplace", "listing_id"], condition=~models.Q(listing_id=""), name="one_ebay_listing_allocation"),
        ]


class QuantityUpdateQuerySet(models.QuerySet):
    def update(self, **kwargs):
        if "diagnostic" in kwargs and kwargs["diagnostic"]:
            validate_diagnostic(kwargs["diagnostic"])
        return super().update(**kwargs)

    def bulk_create(self, objs, **kwargs):
        objs = list(objs)
        for obj in objs:
            obj.clean()
        return super().bulk_create(objs, **kwargs)

    def bulk_update(self, objs, fields, batch_size=None):
        raise ValidationError("Quantity attempts require validated conditional updates.")


class EbayQuantityUpdate(TimeStampedUUIDModel):
    allocation = models.ForeignKey(EbayListingAllocation, on_delete=models.PROTECT, related_name="attempts")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    stock_revision = models.PositiveBigIntegerField()
    allocation_revision = models.PositiveBigIntegerField()
    stock_fingerprint = models.CharField(max_length=64)
    requested_quantity = models.PositiveIntegerField()
    inventory_before = models.PositiveIntegerField(null=True, blank=True)
    offer_before = models.PositiveIntegerField(null=True, blank=True)
    inventory_after = models.PositiveIntegerField(null=True, blank=True)
    offer_after = models.PositiveIntegerField(null=True, blank=True)
    request_sent_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    outcome = models.CharField(max_length=24, default="claimed")
    stock_revision_after = models.PositiveBigIntegerField(null=True, blank=True)
    post_stock_fingerprint = models.CharField(max_length=64, blank=True, default="")
    diagnostic = models.JSONField(default=dict, blank=True)

    objects = QuantityUpdateQuerySet.as_manager()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["allocation"], condition=models.Q(outcome__in=["claimed", "in_flight", "unknown"]), name="one_unresolved_quantity_update")]

    def clean(self):
        if self.diagnostic:
            validate_diagnostic(self.diagnostic)

    def save(self, *args, **kwargs):
        self.clean()
        return super().save(*args, **kwargs)
