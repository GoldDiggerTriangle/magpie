from django.contrib import admin

from apps.valuation.models import (
    FeeSchedule,
    MetalSpotCache,
    ValuationComparable,
    ValuationReport,
)


@admin.register(FeeSchedule)
class FeeScheduleAdmin(admin.ModelAdmin):
    list_display = ("name", "effective_from", "is_active", "final_value_pct", "promoted_pct", "gst_pct")
    list_filter = ("is_active", "effective_from")
    search_fields = ("name", "notes")
    readonly_fields = ("id", "created_at", "updated_at")


class ValuationComparableInline(admin.TabularInline):
    model = ValuationComparable
    extra = 0
    autocomplete_fields = ("comparable",)


@admin.register(ValuationReport)
class ValuationReportAdmin(admin.ModelAdmin):
    list_display = (
        "item",
        "strategy",
        "is_current",
        "estimate_median",
        "suggested_price",
        "confidence_score",
        "created_at",
    )
    list_filter = ("strategy", "is_current", "currency")
    search_fields = ("item__sku", "item__title", "notes", "override_reason")
    autocomplete_fields = ("item", "fee_schedule")
    readonly_fields = ("id", "created_at", "updated_at")
    inlines = [ValuationComparableInline]


@admin.register(ValuationComparable)
class ValuationComparableAdmin(admin.ModelAdmin):
    list_display = ("report", "comparable", "included", "created_at")
    list_filter = ("included",)
    search_fields = ("report__item__sku", "comparable__title", "exclude_reason")
    autocomplete_fields = ("report", "comparable")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(MetalSpotCache)
class MetalSpotCacheAdmin(admin.ModelAdmin):
    list_display = (
        "metal",
        "currency",
        "provider",
        "price_per_gram",
        "provider_price",
        "provider_units",
        "as_of",
        "fetched_at",
    )
    list_filter = ("metal", "currency", "provider")
    readonly_fields = ("id", "created_at", "updated_at")
