"""Append-only fee calendars and sale evidence. No credential/provider payloads."""
from contextlib import contextmanager
from contextvars import ContextVar
import json
import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from apps.core.models import TimeStampedUUIDModel

_writing = ContextVar("fee_evidence_write", default=False)
SECRET = re.compile(r"(?i)(bearer\s+\S+|basic\s+[A-Za-z0-9+/=]{15,}|sk-(?:proj-)?[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{16,}|v\^1\.1#|(?:api_key|token|secret|access_token|refresh_token|client_secret|password|passphrase|authorization)\s*[=:])")


def safe_fee_value(value):
    text = json.dumps(value, default=str)
    if SECRET.search(text):
        raise ValidationError("Secret-bearing fee data is not allowed.")
    if isinstance(value, dict):
        for key, child in value.items():
            if any(part in str(key).lower() for part in ("token", "secret", "password", "passphrase", "header", "raw", "address")):
                raise ValidationError("Fee payload field is not allowed.")
            safe_fee_value(child)
    elif isinstance(value, list):
        for child in value:
            safe_fee_value(child)


@contextmanager
def fee_writes():
    marker = _writing.set(True)
    try:
        yield
    finally:
        _writing.reset(marker)


class ImmutableFeesQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("Fee evidence is immutable; record a new version or adjustment.")

    def delete(self):
        raise ValidationError("Fee evidence cannot be deleted.")

    def bulk_update(self, *args, **kwargs):
        raise ValidationError("Fee evidence cannot be overwritten.")

    def bulk_create(self, objs, **kwargs):
        if not _writing.get() or kwargs.get("update_conflicts"):
            raise ValidationError("Use the validated fee service.")
        for obj in objs:
            obj.full_clean()
            obj.check_payload()
        return super().bulk_create(objs, **kwargs)


class FeeEvidence(TimeStampedUUIDModel):
    objects = ImmutableFeesQuerySet.as_manager()

    class Meta:
        abstract = True

    def check_payload(self):
        for field in self._meta.concrete_fields:
            if isinstance(field, (models.JSONField, models.CharField, models.TextField)):
                safe_fee_value(getattr(self, field.name))
        kind = type(self).__name__
        if kind == "FeeOrderSnapshot":
            from .fee_engine import validate_order
            try:
                validate_order(self.inputs)
            except (ValueError, TypeError, KeyError):
                raise ValidationError("Order snapshot requires the closed fee input schema.") from None
            if set(self.result) - {"state", "label", "rule", "lines", "fee_total", "gst_added", "buyer_incentives_in_fee_base", "version_id", "period_id", "plan", "category_conflicts", "category_unverified"}:
                raise ValidationError("Order result field is not allowed.")
        if kind == "SaleFeeSnapshot":
            allowed = {"actual_fees_total", "actual_fee_breakdown", "estimated_fee_snapshot", "sale_price", "quantity"}
            if not isinstance(self.inputs, dict) or set(self.inputs) - allowed:
                raise ValidationError("Sale snapshot input field is not allowed.")
            if set(self.result) - {"sale_id", "item_sku", "sold_date", "revenue", "fees", "fee_provenance", "seller_mode", "seller_mode_basis", "total_costs", "realised_profit", "all_in_roi", "profit_per_day", "cost_state", "cost_warning", "cost_components", "fee_breakdown", "price_basis", "quantity", "acquired_date", "acquisition_date_basis", "days_held", "days_held_basis"}:
                raise ValidationError("Sale result field is not allowed.")
        if kind == "FeeAdjustment" and set(self.components) - {"fee_delta"}:
            raise ValidationError("Adjustment component is not allowed.")

    def save(self, *args, **kwargs):
        using = kwargs.get("using") or self._state.db or "default"
        if not _writing.get() or not self._state.adding or type(self).objects.using(using).filter(pk=self.pk).exists():
            raise ValidationError("Fee evidence is immutable; use the validated service.")
        self._state.db = using
        self.check_payload()
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Fee evidence cannot be deleted.")


class FeeScheduleVersion(FeeEvidence):
    scope = models.CharField(max_length=30, default="ebay_au")
    marketplace = models.CharField(max_length=20, default="EBAY_AU")
    currency = models.CharField(max_length=3, default="AUD")
    number = models.PositiveIntegerField()
    previous = models.OneToOneField("self", null=True, blank=True, on_delete=models.PROTECT, related_name="next_version")
    label = models.CharField(max_length=120)
    source_url = models.URLField(blank=True, default="")
    source_note = models.TextField()
    entered_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT)
    fingerprint = models.CharField(max_length=64)
    engine_version = models.CharField(max_length=30, default="pro-basic-v1")

    class Meta:
        ordering = ["-number"]
        constraints = [
            models.UniqueConstraint(fields=["scope", "marketplace", "currency", "number"], name="fee_version_number"),
            models.UniqueConstraint(fields=["scope", "marketplace", "currency"], condition=Q(previous__isnull=True), name="fee_calendar_one_root"),
        ]


class FeePlanPeriod(FeeEvidence):
    version = models.ForeignKey(FeeScheduleVersion, on_delete=models.PROTECT, related_name="periods")
    plan = models.CharField(max_length=24)
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    per_order_fee = models.DecimalField(max_digits=10, decimal_places=2)
    international_pct = models.DecimalField(max_digits=9, decimal_places=6)
    gst_treatment = models.CharField(max_length=24, default="inclusive")
    source_note = models.TextField()

    class Meta:
        ordering = ["effective_from"]
        constraints = [
            models.UniqueConstraint(fields=["version", "effective_from"], name="fee_period_start"),
            models.CheckConstraint(condition=Q(effective_to__isnull=True) | Q(effective_to__gt=models.F("effective_from")), name="fee_period_valid_dates"),
            models.CheckConstraint(condition=Q(per_order_fee__gte=0) & Q(international_pct__gte=0), name="fee_period_nonnegative"),
        ]


class FeeTierRate(FeeEvidence):
    period = models.ForeignKey(FeePlanPeriod, on_delete=models.PROTECT, related_name="rates")
    tier = models.CharField(max_length=20)
    fvf_pct = models.DecimalField(max_digits=9, decimal_places=6)
    threshold = models.DecimalField(max_digits=14, decimal_places=2)
    above_pct = models.DecimalField(max_digits=9, decimal_places=6)
    mapping = models.JSONField(default=dict, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["period", "tier"], name="fee_period_tier"),
            models.CheckConstraint(condition=Q(fvf_pct__gte=0) & Q(above_pct__gte=0) & Q(threshold__gt=0), name="fee_tier_valid_rates"),
        ]


class FeeOrderSnapshot(FeeEvidence):
    version = models.ForeignKey(FeeScheduleVersion, null=True, blank=True, on_delete=models.PROTECT)
    period = models.ForeignKey(FeePlanPeriod, null=True, blank=True, on_delete=models.PROTECT)
    channel = models.CharField(max_length=24)
    order_identity = models.CharField(max_length=180)
    sale_date = models.DateField()
    inputs = models.JSONField(default=dict, blank=True)
    result = models.JSONField(default=dict, blank=True)
    fingerprint = models.CharField(max_length=64)
    rule_version = models.CharField(max_length=30, default="unit-largest-remainder-v1")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["channel", "order_identity"], name="fee_order_once")]


class SaleFeeSnapshot(FeeEvidence):
    sale = models.OneToOneField("sales.SaleRecord", on_delete=models.PROTECT, related_name="fee_snapshot")
    order = models.ForeignKey(FeeOrderSnapshot, null=True, blank=True, on_delete=models.PROTECT, related_name="sale_snapshots")
    version = models.ForeignKey(FeeScheduleVersion, null=True, blank=True, on_delete=models.PROTECT)
    provenance = models.CharField(max_length=40)
    basis = models.CharField(max_length=40)
    label = models.CharField(max_length=160)
    inputs = models.JSONField(default=dict, blank=True)
    components = models.JSONField(default=dict, blank=True)
    result = models.JSONField(default=dict, blank=True)


class FeeAdjustment(FeeEvidence):
    snapshot = models.ForeignKey(SaleFeeSnapshot, on_delete=models.PROTECT, related_name="adjustments")
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    reason = models.TextField()
    provenance = models.CharField(max_length=30)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT)
    components = models.JSONField(default=dict, blank=True)
