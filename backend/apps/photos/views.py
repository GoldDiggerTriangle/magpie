from django.db import transaction
from rest_framework.viewsets import ModelViewSet

from apps.photos.models import PhotoAsset
from apps.photos.serializers import PhotoAssetSerializer


class PhotoAssetViewSet(ModelViewSet):
    queryset = PhotoAsset.objects.select_related("item").all()
    serializer_class = PhotoAssetSerializer
    http_method_names = ["get", "patch", "delete", "head", "options"]

    def perform_update(self, serializer):
        with transaction.atomic():
            instance = self.get_object()
            if serializer.validated_data.get("is_main") is True:
                PhotoAsset.objects.filter(item=instance.item, is_main=True).exclude(
                    pk=instance.pk
                ).update(is_main=False)
            serializer.save()
