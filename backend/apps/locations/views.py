from rest_framework.viewsets import ModelViewSet

from apps.locations.models import StorageLocation
from apps.locations.serializers import StorageLocationSerializer


class StorageLocationViewSet(ModelViewSet):
    queryset = StorageLocation.objects.all()
    serializer_class = StorageLocationSerializer
    search_fields = ["label", "notes"]
    filterset_fields = ["type", "parent"]
    ordering_fields = ["label", "created_at"]
    ordering = ["label"]
