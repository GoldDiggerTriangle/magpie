from django.contrib import admin

from apps.audit.models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ["created_at", "actor", "action", "target_type", "target_id"]
    list_filter = ["action", "target_type", "created_at"]
    search_fields = ["actor", "action", "target_type", "target_id"]
    readonly_fields = [
        "actor",
        "action",
        "target_type",
        "target_id",
        "payload",
        "created_at",
        "updated_at",
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
