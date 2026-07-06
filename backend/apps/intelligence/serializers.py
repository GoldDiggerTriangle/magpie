import re

from rest_framework import serializers

from apps.intelligence.models import (
    AICredential,
    AIReferenceLink,
    AIResearchCall,
    AIResearchSearchTerm,
    FieldSuggestion,
    ImageFingerprint,
)


class FieldSuggestionSerializer(serializers.ModelSerializer):
    item_sku = serializers.CharField(source="item.sku", read_only=True)
    item_title = serializers.CharField(source="item.title", read_only=True)
    photo_thumb_url = serializers.SerializerMethodField()
    evidence = serializers.SerializerMethodField()
    audit_metadata = serializers.SerializerMethodField()

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
            "audit_metadata",
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

    def get_evidence(self, obj):
        rationale, _metadata = split_ai_call_metadata(obj.evidence or "")
        return rationale

    def get_audit_metadata(self, obj):
        _rationale, metadata = split_ai_call_metadata(obj.evidence or "")
        return metadata


AI_CALL_PATTERN = re.compile(
    r"(?:\s*\|\s*)AI call ([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})\s*$"
)


def split_ai_call_metadata(evidence: str) -> tuple[str, str]:
    match = AI_CALL_PATTERN.search(evidence or "")
    if not match:
        return evidence, ""
    rationale = evidence[:match.start()].rstrip(" |")
    return rationale, f"AI call {match.group(1)}"


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


class AIStatusSerializer(serializers.Serializer):
    configured = serializers.BooleanField()
    provider = serializers.CharField()
    model_id = serializers.CharField()
    monthly_budget_cap_usd = serializers.CharField()
    monthly_usage_usd = serializers.CharField()
    budget_remaining_usd = serializers.CharField()
    enabled = serializers.BooleanField()
    disabled_reason = serializers.CharField(allow_blank=True)


class AICredentialConfigureSerializer(serializers.Serializer):
    provider = serializers.ChoiceField(
        choices=AICredential.Provider.choices,
        required=False,
        default=AICredential.Provider.OPENAI,
    )
    model_id = serializers.CharField(required=False, allow_blank=True, default="gpt-5.4-mini")
    monthly_budget_cap_usd = serializers.DecimalField(
        max_digits=8,
        decimal_places=2,
        required=False,
        default="5.00",
    )
    api_key = serializers.CharField(write_only=True, trim_whitespace=True, required=False, allow_blank=True)


class AIResearchCallSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIResearchCall
        fields = [
            "id",
            "item",
            "phase",
            "status",
            "provider",
            "model_id",
            "image_count",
            "exif_stripped",
            "suggestions_created",
            "search_terms_created",
            "reference_links_created",
            "input_tokens",
            "output_tokens",
            "estimated_cost_usd",
            "request_metadata",
            "response_metadata",
            "error",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class AIResearchSearchTermSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIResearchSearchTerm
        fields = [
            "id",
            "item",
            "phrase",
            "source_basis",
            "created_by_call",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class AIReferenceLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIReferenceLink
        fields = [
            "id",
            "item",
            "label",
            "url",
            "source_basis",
            "created_by_call",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class AIResearchRunResultSerializer(serializers.Serializer):
    call = AIResearchCallSerializer()
    suggestions = FieldSuggestionSerializer(many=True)
    search_terms = AIResearchSearchTermSerializer(many=True)
    reference_links = AIReferenceLinkSerializer(many=True)
