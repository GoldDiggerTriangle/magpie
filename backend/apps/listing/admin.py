from django.contrib import admin

from apps.listing.models import ChannelListing, ListingBoilerplate, ListingDraft


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


@admin.register(ChannelListing)
class ChannelListingAdmin(admin.ModelAdmin):
    list_display = ["item", "channel", "listed_at", "ended_at", "active"]
    list_filter = ["channel", "ended_at"]
    search_fields = ["item__sku", "item__title", "url", "note"]
    readonly_fields = ["created_at", "updated_at", "source_listing_draft"]
