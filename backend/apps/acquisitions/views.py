from rest_framework.viewsets import ModelViewSet

from apps.acquisitions.models import AcquisitionRecord
from apps.acquisitions.serializers import AcquisitionRecordSerializer


class AcquisitionRecordViewSet(ModelViewSet):
    queryset = AcquisitionRecord.objects.all()
    serializer_class = AcquisitionRecordSerializer
    search_fields = ["source", "travel_notes", "notes"]
    filterset_fields = ["currency"]
    ordering_fields = ["acquired_on", "created_at", "total_cost"]
    ordering = ["-acquired_on", "-created_at"]
