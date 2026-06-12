from rest_framework import serializers

from apps.ebay.models import EbayAccountSnapshot, MerchantLocation


class ConnectCompleteSerializer(serializers.Serializer):
    pasted_url = serializers.CharField(required=False, allow_blank=False, trim_whitespace=False)
    code = serializers.CharField(required=False, allow_blank=False, trim_whitespace=False)
    state = serializers.CharField(required=False, allow_blank=False)

    def validate(self, attrs):
        if attrs.get("pasted_url"):
            return attrs
        if attrs.get("code") and attrs.get("state"):
            return attrs
        raise serializers.ValidationError(
            "Provide pasted_url or both code and state."
        )


class EbayAccountSnapshotSerializer(serializers.ModelSerializer):
    policy_counts = serializers.SerializerMethodField()
    opted_in = serializers.BooleanField(source="business_policies_opted_in")

    class Meta:
        model = EbayAccountSnapshot
        fields = ["opted_in", "policy_counts", "fetched_at"]
        read_only_fields = fields

    def get_policy_counts(self, obj) -> dict[str, int]:
        return {
            "payment": len(obj.payment_policies or []),
            "fulfillment": len(obj.fulfillment_policies or []),
            "return": len(obj.return_policies or []),
        }


class MerchantLocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = MerchantLocation
        fields = [
            "environment",
            "merchant_location_key",
            "name",
            "country",
            "postal_code",
            "city",
            "state",
            "created_on_ebay",
            "fetched_at",
        ]
        read_only_fields = fields


class MerchantLocationCreateSerializer(serializers.Serializer):
    merchant_location_key = serializers.CharField(max_length=36)
    name = serializers.CharField(max_length=1000)
    country = serializers.CharField(max_length=2)
    postal_code = serializers.CharField(max_length=16, required=False, allow_blank=True)
    city = serializers.CharField(max_length=128, required=False, allow_blank=True)
    state = serializers.CharField(max_length=128, required=False, allow_blank=True)


class CategoryAspectsQuerySerializer(serializers.Serializer):
    category_id = serializers.CharField(max_length=40)


class CategorySuggestionsQuerySerializer(serializers.Serializer):
    q = serializers.CharField(max_length=120)
