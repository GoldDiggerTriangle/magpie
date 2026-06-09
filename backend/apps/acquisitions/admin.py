from django.contrib import admin

from apps.acquisitions.models import AcquisitionRecord


@admin.register(AcquisitionRecord)
class AcquisitionRecordAdmin(admin.ModelAdmin):
    list_display = ("source", "acquired_on", "total_cost", "currency")
    list_filter = ("currency", "acquired_on")
    search_fields = ("source", "travel_notes", "notes")
    readonly_fields = ("id", "created_at", "updated_at")
