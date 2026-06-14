from rest_framework import serializers

from apps.inventory.models import InventoryItem
from apps.sales.models import SaleRecord
from apps.sales.services import create_sale_record


class SaleRecordSerializer(serializers.ModelSerializer):
    item = serializers.PrimaryKeyRelatedField(
        queryset=InventoryItem.objects.all(),
        required=False,
        allow_null=True,
    )
    net_proceeds = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    allocated_cost_basis = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        read_only=True,
        allow_null=True,
    )
    realised_profit = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        read_only=True,
        allow_null=True,
    )
    corrected_from = serializers.UUIDField(source="corrected_from_id", read_only=True)
    is_superseded = serializers.BooleanField(read_only=True)
    item_sku = serializers.SerializerMethodField()
    item_title = serializers.SerializerMethodField()

    class Meta:
        model = SaleRecord
        fields = [
            "id",
            "item",
            "item_sku",
            "item_title",
            "sale_date",
            "quantity",
            "sale_price",
            "channel",
            "is_external",
            "cost_basis_unknown",
            "actual_fees_total",
            "actual_fee_breakdown",
            "fee_status",
            "actual_shipping_cost",
            "net_proceeds",
            "allocated_cost_basis",
            "realised_profit",
            "cost_basis_override",
            "listing_draft",
            "valuation_snapshot",
            "estimated_fee_snapshot",
            "provenance",
            "ebay_order_id",
            "ebay_line_item_id",
            "ebay_transaction_id",
            "channel_data",
            "corrected_from",
            "is_superseded",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "item_sku",
            "item_title",
            "is_external",
            "cost_basis_unknown",
            "net_proceeds",
            "allocated_cost_basis",
            "realised_profit",
            "valuation_snapshot",
            "estimated_fee_snapshot",
            "corrected_from",
            "is_superseded",
            "provenance",
            "ebay_order_id",
            "ebay_line_item_id",
            "ebay_transaction_id",
            "channel_data",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        item = attrs.get("item") or self.context.get("item")
        is_external = attrs.get("is_external", False)
        if item is None and not is_external:
            raise serializers.ValidationError({"item": ["This field is required."]})
        attrs["item"] = item

        listing_draft = attrs.get("listing_draft")
        if listing_draft is not None and (item is None or listing_draft.item_id != item.id):
            raise serializers.ValidationError(
                {"listing_draft": ["Listing draft must belong to the sale item."]}
            )

        if attrs.get("provenance") == SaleRecord.Provenance.EBAY_SYNC:
            raise serializers.ValidationError(
                {"provenance": ["eBay sync provenance is reserved for the sync sprint."]}
            )
        return attrs

    def get_item_sku(self, obj):
        return obj.item.sku if obj.item_id and obj.item else ""

    def get_item_title(self, obj):
        return obj.item.title if obj.item_id and obj.item else "External sale"

    def create(self, validated_data):
        return create_sale_record(
            data=validated_data,
            corrected_from=self.context.get("corrected_from"),
        )
