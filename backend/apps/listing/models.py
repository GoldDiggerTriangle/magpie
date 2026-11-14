from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.signals import pre_delete
from django.dispatch import receiver
from django.utils import timezone

from apps.core.models import TimeStampedUUIDModel
from apps.listing.canonical_check import CONSTRAINT_NAME
from apps.listing.draft_status import IN_FLIGHT_DRAFT_STATUSES, active_draft_filter, read_only_draft_filter


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


class ListingDraftQuerySet(models.QuerySet):
    def assert_mutable(self):
        if self.filter(read_only_draft_filter()).exists():
            raise ValidationError("Published and archived drafts are read-only; create a relisting draft instead.")

    def update(self, **kwargs):
        self.assert_mutable()
        return super().update(**kwargs)

    def bulk_update(self, objs, fields, batch_size=None):
        objs = tuple(objs)
        self.filter(pk__in=[obj.pk for obj in objs]).assert_mutable()
        return super().bulk_update(objs, fields, batch_size=batch_size)


class ListingDraft(TimeStampedUUIDModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        READY = "ready", "Ready"
        EXPORTED = "exported", "Exported"
        STAGED = "staged", "Staged"
        PUBLISHED = "published", "Published"
        PUBLISH_FAILED = "publish_failed", "Publish failed"
        ARCHIVED = "archived", "Archived"
        PUBLISHING = "publishing", "Publishing"
        PUBLISH_UNKNOWN = "publish_unknown", "Publish outcome unknown"

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

    objects = ListingDraftQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["item", "channel"], condition=active_draft_filter(),
                name=CONSTRAINT_NAME,
            ),
        ]
        indexes = [
            models.Index(fields=["item"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self) -> str:
        return f"{self.item.sku} listing draft ({self.status})"

    @property
    def is_read_only(self):
        return type(self).objects.using(self._state.db).filter(pk=self.pk).filter(read_only_draft_filter()).exists()

    def assert_editable(self):
        if self.is_read_only:
            raise ValidationError("Published and archived drafts are read-only; create a relisting draft instead.")
        if self.status in IN_FLIGHT_DRAFT_STATUSES:
            raise ValidationError("Reconcile the publish outcome before editing this draft.")

    def save(self, *args, **kwargs):
        using = kwargs.get("using") or self._state.db
        type(self).objects.using(using).filter(pk=self.pk).assert_mutable()
        return super().save(*args, **kwargs)


@receiver(pre_delete, sender=ListingDraft)
def protect_listing_history(sender, instance, using, **kwargs):
    # The signal also covers queryset deletes and an inventory-item cascade.
    sender.objects.using(using).filter(pk=instance.pk).assert_mutable()
    raise ValidationError("Listing drafts are retained as history. Archive instead of deleting.")


class ChannelListing(TimeStampedUUIDModel):
    class Channel(models.TextChoices):
        EBAY = "ebay", "eBay"
        FACEBOOK_MARKETPLACE = "facebook_marketplace", "Facebook Marketplace"
        GUMTREE = "gumtree", "Gumtree"
        IN_PERSON = "in_person", "In person"
        OTHER = "other", "Other"

    item = models.ForeignKey(
        "inventory.InventoryItem",
        on_delete=models.CASCADE,
        related_name="channel_listings",
    )
    channel = models.CharField(
        max_length=40,
        choices=Channel.choices,
        default=Channel.OTHER,
    )
    listed_at = models.DateTimeField(default=timezone.now)
    ended_at = models.DateTimeField(null=True, blank=True)
    url = models.URLField(max_length=500, blank=True, default="")
    note = models.TextField(blank=True, default="")
    source_listing_draft = models.OneToOneField(
        "listing.ListingDraft",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="channel_listing",
    )

    class Meta:
        ordering = ["channel", "-listed_at"]
        indexes = [
            models.Index(fields=["item", "ended_at"], name="chan_list_item_active_idx"),
            models.Index(fields=["channel", "ended_at"], name="chan_list_chan_active_idx"),
            models.Index(fields=["listed_at"], name="channel_listing_listed_idx"),
        ]

    @property
    def active(self) -> bool:
        return self.ended_at is None

    def __str__(self) -> str:
        state = "active" if self.active else "ended"
        return f"{self.item.sku} {self.get_channel_display()} listing ({state})"
