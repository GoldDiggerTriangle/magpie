from django.contrib import admin

from apps.profit.models import ProfitSetting


@admin.register(ProfitSetting)
class ProfitSettingAdmin(admin.ModelAdmin):
    list_display = ["seller_mode", "default_roi_pct", "default_roi_basis", "maybe_band_pct", "updated_at"]
