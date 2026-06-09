from django.db import models

from apps.core.models import TimeStampedUUIDModel


class AcquisitionRecord(TimeStampedUUIDModel):
    source = models.CharField(max_length=200, blank=True, default="")
    acquired_on = models.DateField(null=True, blank=True)
    total_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )
    currency = models.CharField(max_length=3, default="AUD")
    travel_notes = models.TextField(blank=True, default="")
    notes = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-acquired_on", "-created_at"]

    def __str__(self) -> str:
        return self.source or f"Acquisition {self.id}"
