from rest_framework import serializers

from apps.inventory.models import InventoryItem
from apps.sales.models import SaleRecord
from apps.sales.services import create_sale_record


class SaleRecordSerializer(serializers.ModelSerializer):
    item = serializers.PrimaryKeyRelatedField(
        queryset=InventoryItem.objects.all(),
        required=False,
    )
    net_proceeds = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    allocated_cost_basis = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    realised_profit = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    corrected_from = serializers.UUIDField(source="corrected_from_id", read_only=True)
    is_superseded = serializers.BooleanField(read_only=True)
    item_sku = serializers.CharField(source="item.sku", read_only=True)
    item_title = serializers.CharField(source="item.title", read_only=True)

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
            "actual_fees_total",
            "actual_fee_breakdown",
            "actual_shipping_cost",
            "net_proceeds",
            "allocated_cost_basis",
            "realised_profit",
            "cost_basis_override",
            "listing_draft",
            "valuation_snapshot",
            "estimated_fee_snapshot",
            "provenance",
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
            "net_proceeds",
            "allocated_cost_basis",
            "realised_profit",
            "valuation_snapshot",
            "estimated_fee_snapshot",
            "corrected_from",
            "is_superseded",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        item = attrs.get("item") or self.context.get("item")
        if item is None:
            raise serializers.ValidationError({"item": ["This field is required."]})
        attrs["item"] = item

        listing_draft = attrs.get("listing_draft")
        if listing_draft is not None and listing_draft.item_id != item.id:
            raise serializers.ValidationError(
                {"listing_draft": ["Listing draft must belong to the sale item."]}
            )

        if attrs.get("provenance") == SaleRecord.Provenance.EBAY_SYNC:
            raise serializers.ValidationError(
                {"provenance": ["eBay sync provenance is reserved for the sync sprint."]}
            )
        return attrs

    def create(self, validated_data):
        return create_sale_record(
            data=validated_data,
            corrected_from=self.context.get("corrected_from"),
        )
