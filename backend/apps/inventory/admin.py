from django.contrib import admin

from apps.inventory.models import InventoryItem


@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = (
        "sku",
        "title",
        "category",
        "status",
        "condition",
        "location",
        "estimated_value",
        "currency",
        "created_at",
    )
    list_filter = ("status", "condition", "category", "location", "currency")
    search_fields = ("sku", "title", "notes")
    readonly_fields = ("id", "sku", "created_at", "updated_at")
    autocomplete_fields = ("category", "location", "acquisition", "owner")
    fieldsets = (
        (
            "Core",
            {
                "fields": (
                    "id",
                    "sku",
                    "title",
                    "category",
                    "status",
                    "condition",
                    "location",
                    "acquisition",
                    "owner",
                )
            },
        ),
        (
            "Pricing",
            {
                "fields": (
                    "acquisition_cost",
                    "refurb_cost",
                    "inbound_shipping_cost",
                    "est_outbound_shipping",
                    "est_packaging_cost",
                    "estimated_value",
                    "min_price",
                    "target_price",
                    "currency",
                )
            },
        ),
        ("Details", {"fields": ("attributes", "notes")}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )
