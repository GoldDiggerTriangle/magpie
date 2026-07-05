from rest_framework import serializers

from apps.research.models import Comparable, ResearchRecord


class ComparableSerializer(serializers.ModelSerializer):
    class Meta:
        model = Comparable
        fields = [
            "id",
            "item",
            "descriptor_category",
            "descriptor_terms",
            "descriptor_attributes",
            "kind",
            "source",
            "title",
            "price",
            "price_basis",
            "shipping",
            "currency",
            "condition",
            "grade",
            "sale_format",
            "source_tag",
            "match_scope",
            "match_reason",
            "url",
            "observed_on",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
        extra_kwargs = {"item": {"required": False, "allow_null": True}}

    def validate_source_tag(self, value):
        if not value:
            return ""
        return "_".join(value.strip().lower().split())[:80]


class ResearchRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResearchRecord
        fields = [
            "id",
            "item",
            "source",
            "content",
            "links",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_links(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("Expected a list of link objects.")
        for index, link in enumerate(value):
            if not isinstance(link, dict):
                raise serializers.ValidationError(f"Link {index + 1} must be an object.")
            label = link.get("label")
            url = link.get("url")
            if not isinstance(label, str) or not label.strip():
                raise serializers.ValidationError(f"Link {index + 1} requires a label.")
            if not isinstance(url, str) or not url.strip():
                raise serializers.ValidationError(f"Link {index + 1} requires a url.")
        return value

