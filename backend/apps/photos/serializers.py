from rest_framework import serializers

from apps.photos.models import PhotoAsset
from integrations.storage import LocalFileStorageAdapter


class PhotoAssetSerializer(serializers.ModelSerializer):
    original_url = serializers.SerializerMethodField()
    processed_url = serializers.SerializerMethodField()
    thumb_url = serializers.SerializerMethodField()

    class Meta:
        model = PhotoAsset
        fields = [
            "id",
            "item",
            "role",
            "is_main",
            "order_index",
            "original_path",
            "processed_path",
            "thumb_path",
            "original_url",
            "processed_url",
            "thumb_url",
            "width",
            "height",
            "bytes_original",
            "exif_stripped",
            "quality_score",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "item",
            "original_path",
            "processed_path",
            "thumb_path",
            "original_url",
            "processed_url",
            "thumb_url",
            "width",
            "height",
            "bytes_original",
            "exif_stripped",
            "quality_score",
            "created_at",
            "updated_at",
        ]

    def get_original_url(self, obj):
        return self.get_url(obj.original_path)

    def get_processed_url(self, obj):
        return self.get_url(obj.processed_path)

    def get_thumb_url(self, obj):
        return self.get_url(obj.thumb_path)

    def get_url(self, key: str):
        if not key:
            return None
        storage = self.context.get("storage") or LocalFileStorageAdapter()
        return storage.url(key)
