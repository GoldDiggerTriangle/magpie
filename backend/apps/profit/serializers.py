from rest_framework import serializers

from apps.profit.models import Lot, ProfitSetting, Source


class ProfitSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProfitSetting
        fields = [
            "seller_mode",
            "pro_other_final_value_pct",
            "manual_final_value_pct",
            "manual_fixed_fee",
            "default_flat_profit_target",
            "default_roi_pct",
            "default_roi_basis",
            "maybe_band_pct",
            "schema_version",
            "updated_at",
        ]
        read_only_fields = ["schema_version", "updated_at"]


class SourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Source
        fields = ["id", "name", "type", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class LotSerializer(serializers.ModelSerializer):
    source_detail = SourceSerializer(source="source", read_only=True)
    allocated = serializers.CharField(read_only=True)
    unallocated = serializers.CharField(read_only=True)
    tally_label = serializers.CharField(read_only=True)
    members = serializers.ListField(read_only=True)
    pnl = serializers.DictField(read_only=True)
    warning = serializers.CharField(read_only=True)
    is_partially_allocated = serializers.BooleanField(read_only=True)
    is_over_allocated = serializers.BooleanField(read_only=True)
    proportional_available = serializers.BooleanField(read_only=True)

    class Meta:
        model = Lot
        fields = [
            "id",
            "label",
            "purchase_date",
            "total_cost",
            "source",
            "source_detail",
            "note",
            "allocated",
            "unallocated",
            "tally_label",
            "members",
            "pnl",
            "warning",
            "is_partially_allocated",
            "is_over_allocated",
            "proportional_available",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "source_detail",
            "allocated",
            "unallocated",
            "tally_label",
            "members",
            "pnl",
            "warning",
            "is_partially_allocated",
            "is_over_allocated",
            "proportional_available",
            "created_at",
            "updated_at",
        ]

    def to_representation(self, instance):
        from apps.profit.lots import lot_summary

        return lot_summary(instance)


class LotAllocationLineSerializer(serializers.Serializer):
    item = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)


class LotManualAllocationSerializer(serializers.Serializer):
    allocations = LotAllocationLineSerializer(many=True)


class LotScrapSerializer(serializers.Serializer):
    item = serializers.UUIDField()
    scrapped_at = serializers.DateField(required=False)
