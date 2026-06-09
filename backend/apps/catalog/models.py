from django.db import models

from apps.core.models import TimeStampedUUIDModel


class ProductCategory(TimeStampedUUIDModel):
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True)
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="children",
    )
    sku_prefix = models.CharField(max_length=12, default="GSP")
    profile_key = models.CharField(max_length=60, blank=True, default="")
    description = models.TextField(blank=True, default="")

    class Meta:
        verbose_name_plural = "product categories"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name
