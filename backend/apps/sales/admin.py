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
        "is_external",
        "fee_status",
        "corrected_from",
    )
    list_filter = ("channel", "provenance", "is_external", "fee_status", "sale_date")
    search_fields = ("item__sku", "item__title", "ebay_order_id", "ebay_line_item_id", "notes")
