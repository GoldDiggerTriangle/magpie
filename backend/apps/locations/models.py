from django.db import models

from apps.core.models import TimeStampedUUIDModel


class StorageLocation(TimeStampedUUIDModel):
    class LocationType(models.TextChoices):
        SHED = "shed", "Shed"
        ROOM = "room", "Room"
        SHELF = "shelf", "Shelf"
        BIN = "bin", "Bin"
        BOX = "box", "Box"
        OTHER = "other", "Other"

    label = models.CharField(max_length=120)
    type = models.CharField(
        max_length=20,
        choices=LocationType.choices,
        default=LocationType.BOX,
    )
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="children",
    )
    notes = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["label"]

    def __str__(self) -> str:
        return self.label
