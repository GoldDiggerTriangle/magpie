from rest_framework import serializers

from apps.ebay.models import EbayAccountSnapshot


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
