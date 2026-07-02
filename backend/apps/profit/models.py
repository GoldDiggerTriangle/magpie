from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models

from apps.core.models import TimeStampedUUIDModel


class ProfitSetting(TimeStampedUUIDModel):
    class SellerMode(models.TextChoices):
        FREE_SELLING = "free_selling", "Free selling"
        PRO_STARTER = "pro_starter", "Pro Starter"
        PRO_OTHER = "pro_other", "Pro Basic or above"
        LEGACY_MANUAL = "legacy_manual", "Legacy / manual"

    class RoiBasis(models.TextChoices):
        ALL_IN_CASH = "all_in_cash", "All-in cash"
        BUY_PRICE = "buy_price", "On buy price"

    seller_mode = models.CharField(
        max_length=24,
        choices=SellerMode.choices,
        default=SellerMode.FREE_SELLING,
    )
    pro_other_final_value_pct = models.DecimalField(max_digits=6, decimal_places=3, default=Decimal("13.400"))
    manual_final_value_pct = models.DecimalField(max_digits=6, decimal_places=3, default=Decimal("0"))
    manual_fixed_fee = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("0"))
    default_flat_profit_target = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("25"))
    default_roi_pct = models.DecimalField(max_digits=7, decimal_places=3, default=Decimal("30"))
    default_roi_basis = models.CharField(
        max_length=20,
        choices=RoiBasis.choices,
        default=RoiBasis.ALL_IN_CASH,
    )
    maybe_band_pct = models.DecimalField(max_digits=6, decimal_places=3, default=Decimal("10"))
    schema_version = models.PositiveSmallIntegerField(default=1)

    class Meta:
        ordering = ["-updated_at"]

    def clean(self) -> None:
        if self.pro_other_final_value_pct < 0:
            raise ValidationError({"pro_other_final_value_pct": "Percentage cannot be negative."})
        if self.manual_final_value_pct < 0:
            raise ValidationError({"manual_final_value_pct": "Percentage cannot be negative."})
        if self.manual_fixed_fee < 0:
            raise ValidationError({"manual_fixed_fee": "Fee cannot be negative."})
        if self.default_flat_profit_target < 0:
            raise ValidationError({"default_flat_profit_target": "Target cannot be negative."})
        if self.default_roi_pct < 0:
            raise ValidationError({"default_roi_pct": "ROI cannot be negative."})
        if self.maybe_band_pct < 0:
            raise ValidationError({"maybe_band_pct": "Band cannot be negative."})

    def save(self, *args, **kwargs) -> None:
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return "Profit settings"


def current_profit_setting() -> ProfitSetting:
    return ProfitSetting.objects.order_by("-updated_at").first() or ProfitSetting()
