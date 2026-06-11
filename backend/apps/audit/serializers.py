from rest_framework import serializers

from apps.audit.models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditLog
        fields = [
            "id",
            "actor",
            "action",
            "target_type",
            "target_id",
            "payload",
            "created_at",
        ]
        read_only_fields = fields
