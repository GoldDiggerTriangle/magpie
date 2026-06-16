from rest_framework import serializers

from apps.photos.models import PhotoAsset, PhotoDerivative
from integrations.storage import LocalFileStorageAdapter


class MediaUrlMixin:
    def get_url(self, key: str):
        if not key:
            return None
        storage = self.context.get("storage") or LocalFileStorageAdapter()
        return storage.url(key)


class PhotoDerivativeSerializer(MediaUrlMixin, serializers.ModelSerializer):
    fixed_url = serializers.SerializerMethodField()
    thumb_url = serializers.SerializerMethodField()
    source_url = serializers.SerializerMethodField()

    class Meta:
        model = PhotoDerivative
        fields = [
            "id",
            "photo",
            "status",
            "source",
            "fixed_path",
            "thumb_path",
            "source_path",
            "fixed_url",
            "thumb_url",
            "source_url",
            "width",
            "height",
            "bytes_fixed",
            "pipeline_version",
            "operations",
            "parameters",
            "background_mode",
            "condition_note",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_fixed_url(self, obj):
        return self.get_url(obj.fixed_path)

    def get_thumb_url(self, obj):
        return self.get_url(obj.thumb_path)

    def get_source_url(self, obj):
        return self.get_url(obj.source_path)


class PhotoAssetSerializer(MediaUrlMixin, serializers.ModelSerializer):
    original_url = serializers.SerializerMethodField()
    processed_url = serializers.SerializerMethodField()
    thumb_url = serializers.SerializerMethodField()
    derivatives = PhotoDerivativeSerializer(many=True, read_only=True)
    pending_derivative = serializers.SerializerMethodField()
    active_derivative_detail = serializers.SerializerMethodField()

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
            "fixup_status",
            "active_derivative",
            "active_derivative_detail",
            "pending_derivative",
            "derivatives",
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
            "fixup_status",
            "active_derivative",
            "active_derivative_detail",
            "pending_derivative",
            "derivatives",
            "created_at",
            "updated_at",
        ]

    def get_original_url(self, obj):
        return self.get_url(obj.original_path)

    def get_processed_url(self, obj):
        return self.get_url(obj.processed_path)

    def get_thumb_url(self, obj):
        return self.get_url(obj.thumb_path)

    def get_pending_derivative(self, obj):
        pending = next(
            (
                derivative
                for derivative in getattr(obj, "_prefetched_objects_cache", {})
                .get("derivatives", [])
                if derivative.status == PhotoDerivative.Status.PENDING_REVIEW
            ),
            None,
        )
        if pending is None:
            pending = obj.derivatives.filter(
                status=PhotoDerivative.Status.PENDING_REVIEW
            ).order_by("-created_at").first()
        return (
            PhotoDerivativeSerializer(pending, context=self.context).data
            if pending
            else None
        )

    def get_active_derivative_detail(self, obj):
        if obj.active_derivative_id is None:
            return None
        derivative = getattr(obj, "active_derivative", None)
        return (
            PhotoDerivativeSerializer(derivative, context=self.context).data
            if derivative
            else None
        )
