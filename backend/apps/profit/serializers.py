from rest_framework import serializers

from apps.profit.models import ProfitSetting


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
