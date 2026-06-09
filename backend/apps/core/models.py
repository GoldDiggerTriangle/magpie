import uuid

from django.db import models


class TimeStampedUUIDModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class SkuSequence(models.Model):
    """One incrementing counter per SKU prefix. Locked on increment."""

    prefix = models.CharField(max_length=12, primary_key=True)
    last_value = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["prefix"]

    def __str__(self) -> str:
        return f"{self.prefix}: {self.last_value}"
