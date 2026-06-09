from django.contrib import admin

from apps.research.models import Comparable, ResearchRecord


@admin.register(Comparable)
class ComparableAdmin(admin.ModelAdmin):
    list_display = ("title", "item", "kind", "source", "price", "currency", "observed_on")
    list_filter = ("kind", "currency", "observed_on")
    search_fields = ("title", "source", "notes", "url", "item__sku", "item__title")
    autocomplete_fields = ("item",)
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(ResearchRecord)
class ResearchRecordAdmin(admin.ModelAdmin):
    list_display = ("source", "item", "created_at")
    search_fields = ("source", "content", "item__sku", "item__title")
    autocomplete_fields = ("item",)
    readonly_fields = ("id", "created_at", "updated_at")
