from django.contrib import admin

from apps.locations.models import StorageLocation


@admin.register(StorageLocation)
class StorageLocationAdmin(admin.ModelAdmin):
    list_display = ("label", "type", "parent")
    list_filter = ("type",)
    search_fields = ("label", "notes")
    readonly_fields = ("id", "created_at", "updated_at")
