from django.contrib import admin

from apps.listing.models import ListingBoilerplate, ListingDraft


@admin.register(ListingBoilerplate)
class ListingBoilerplateAdmin(admin.ModelAdmin):
    list_display = ["name", "channel", "is_active", "updated_at"]
    list_filter = ["channel", "is_active"]
    search_fields = ["name", "notes", "body_html"]


@admin.register(ListingDraft)
class ListingDraftAdmin(admin.ModelAdmin):
    list_display = ["item", "status", "channel", "price", "currency", "exported_at"]
    list_filter = ["status", "channel", "listing_format", "currency"]
    search_fields = ["item__sku", "item__title", "title", "subtitle"]
    readonly_fields = ["generated_meta", "exported_at", "created_at", "updated_at"]
