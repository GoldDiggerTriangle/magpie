from django.contrib import admin

from apps.dashboard.models import DashboardPreference


@admin.register(DashboardPreference)
class DashboardPreferenceAdmin(admin.ModelAdmin):
    list_display = ["id", "schema_version", "updated_at"]
    readonly_fields = ["created_at", "updated_at"]
