from rest_framework import serializers

from apps.intelligence.models import FieldSuggestion, ImageFingerprint


class FieldSuggestionSerializer(serializers.ModelSerializer):
    item_sku = serializers.CharField(source="item.sku", read_only=True)
    item_title = serializers.CharField(source="item.title", read_only=True)
    photo_thumb_url = serializers.SerializerMethodField()

    class Meta:
        model = FieldSuggestion
        fields = [
            "id",
            "item",
            "item_sku",
            "item_title",
            "photo",
            "photo_thumb_url",
            "field",
            "proposed_value",
            "source",
            "confidence_band",
            "evidence",
            "status",
            "resolved_value",
            "resolved_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_photo_thumb_url(self, obj):
        if not obj.photo_id or not obj.photo or not obj.photo.thumb_path:
            return None
        from apps.photos.serializers import PhotoAssetSerializer

        return PhotoAssetSerializer(context=self.context).get_url(obj.photo.thumb_path)


class FieldSuggestionResolveSerializer(serializers.Serializer):
    value = serializers.JSONField(required=False)


class ImageFingerprintSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImageFingerprint
        fields = [
            "id",
            "photo",
            "item",
            "perceptual_hash",
            "algorithm",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class SoldSearchLinkSerializer(serializers.Serializer):
    id = serializers.CharField()
    label = serializers.CharField()
    query = serializers.CharField()
    url = serializers.URLField()


class OcrRunResultSerializer(serializers.Serializer):
    available = serializers.BooleanField()
    detail = serializers.CharField()
    suggestions = FieldSuggestionSerializer(many=True)
