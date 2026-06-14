from rest_framework import serializers

from apps.catalog.models import ProductCategory
from apps.ebay.models import (
    EbayAccountSnapshot,
    EbayOrderDuplicateCandidate,
    EbayOrderStaging,
    MerchantLocation,
)
from apps.inventory.models import InventoryItem


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


class EbayOrderStagingSerializer(serializers.ModelSerializer):
    class Meta:
        model = EbayOrderStaging
        fields = [
            "id",
            "environment",
            "ebay_order_id",
            "ebay_line_item_id",
            "sku",
            "quantity",
            "line_price",
            "sale_date",
            "actual_fee",
            "fee_status",
            "buyer_region",
            "status",
            "resolved_sale",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class EbayOrderDuplicateCandidateSerializer(serializers.ModelSerializer):
    item_sku = serializers.CharField(source="item.sku", read_only=True)
    item_title = serializers.CharField(source="item.title", read_only=True)
    manual_sale_id = serializers.UUIDField(source="manual_sale.id", read_only=True)

    class Meta:
        model = EbayOrderDuplicateCandidate
        fields = [
            "id",
            "environment",
            "ebay_order_id",
            "ebay_line_item_id",
            "sku",
            "item",
            "item_sku",
            "item_title",
            "manual_sale_id",
            "quantity",
            "line_price",
            "sale_date",
            "status",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class EbayOrderSyncSerializer(serializers.Serializer):
    first_sync_days = serializers.IntegerField(min_value=1, max_value=365, required=False)
    lookback_days = serializers.IntegerField(min_value=0, max_value=30, required=False)


class EbayOrderStagingResolveSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["link", "quick_create", "mark_external"])
    item = serializers.PrimaryKeyRelatedField(
        queryset=InventoryItem.objects.all(),
        required=False,
        allow_null=True,
    )
    title = serializers.CharField(max_length=200, required=False, allow_blank=True)
    category = serializers.PrimaryKeyRelatedField(
        queryset=ProductCategory.objects.all(),
        required=False,
        allow_null=True,
    )
    quantity_total = serializers.IntegerField(min_value=1, required=False)
    acquisition_cost = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        allow_null=True,
    )
    estimated_value = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        allow_null=True,
    )
    cost_basis_override = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        allow_null=True,
    )
    notes = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        action = attrs["action"]
        if action == "link" and not attrs.get("item"):
            raise serializers.ValidationError({"item": ["Select an item to link."]})
        return attrs

    @property
    def item_data(self):
        return {
            key: self.validated_data.get(key)
            for key in ["title", "category", "quantity_total", "acquisition_cost", "estimated_value", "notes"]
            if key in self.validated_data
        }


class EbayOrderDuplicateResolveSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["link", "dismiss"])
