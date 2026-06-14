from django.contrib import admin

from apps.sales.models import SaleRecord


@admin.register(SaleRecord)
class SaleRecordAdmin(admin.ModelAdmin):
    list_display = (
        "item",
        "sale_date",
        "quantity",
        "sale_price",
        "channel",
        "provenance",
        "corrected_from",
    )
    list_filter = ("channel", "provenance", "sale_date")
    search_fields = ("item__sku", "item__title", "notes")
