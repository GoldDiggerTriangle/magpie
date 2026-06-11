from rest_framework.viewsets import ReadOnlyModelViewSet

from apps.audit.models import AuditLog
from apps.audit.serializers import AuditLogSerializer


class AuditLogViewSet(ReadOnlyModelViewSet):
    serializer_class = AuditLogSerializer
    http_method_names = ["get", "head", "options"]
    ordering = ["-created_at"]

    def get_queryset(self):
        queryset = AuditLog.objects.all()
        action_prefix = self.request.query_params.get("action_prefix")
        target_type = self.request.query_params.get("target_type")
        if action_prefix:
            queryset = queryset.filter(action__startswith=action_prefix)
        if target_type:
            queryset = queryset.filter(target_type=target_type)
        return queryset
