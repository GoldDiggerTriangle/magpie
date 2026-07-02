from django.db import transaction
from rest_framework import serializers

from apps.research.models import Comparable
from apps.valuation.models import FeeSchedule, ValuationComparable, ValuationReport
from apps.valuation.services import (
    active_fee_schedule,
    calculate_profit,
    true_cost_for_item,
)
from apps.valuation.strategies import get_strategy
from integrations.metals import MetalsUnavailable


DERIVED_FIELDS = {
    "estimate_low": "low",
    "estimate_median": "median",
    "estimate_high": "high",
    "suggested_price": "suggested",
    "fast_sale_price": "fast_sale",
    "patient_price": "patient",
    "min_acceptable_price": "min_acceptable",
}


class FeeScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeeSchedule
        fields = [
            "id",
            "name",
            "effective_from",
            "is_active",
            "seller_mode",
            "price_basis",
            "buyer_protection_fee_enabled",
            "international_delivery_pct",
            "final_value_pct",
            "per_order_fee",
            "promoted_pct",
            "gst_pct",
            "default_packaging_cost",
            "default_outbound_shipping",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class ComparableSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Comparable
        fields = [
            "id",
            "kind",
            "source",
            "title",
            "price",
            "shipping",
            "currency",
            "condition",
            "url",
            "observed_on",
            "notes",
        ]


class ValuationComparableSerializer(serializers.ModelSerializer):
    comparable_summary = ComparableSummarySerializer(source="comparable", read_only=True)

    class Meta:
        model = ValuationComparable
        fields = [
            "id",
            "comparable",
            "comparable_summary",
            "included",
            "exclude_reason",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "comparable_summary", "created_at", "updated_at"]

    def validate(self, data):
        included = data.get("included", True)
        exclude_reason = data.get("exclude_reason", "")
        if included is False and not exclude_reason.strip():
            raise serializers.ValidationError(
                {"exclude_reason": "Excluded comparables require an exclusion reason."}
            )
        return data


class ValuationReportSerializer(serializers.ModelSerializer):
    comp_links = ValuationComparableSerializer(many=True, required=False)
    profit_projection = serializers.SerializerMethodField()

    class Meta:
        model = ValuationReport
        fields = [
            "id",
            "item",
            "strategy",
            "is_current",
            "estimate_low",
            "estimate_median",
            "estimate_high",
            "suggested_price",
            "fast_sale_price",
            "patient_price",
            "min_acceptable_price",
            "currency",
            "confidence_score",
            "confidence_reason",
            "is_overridden",
            "override_reason",
            "inputs",
            "fee_schedule",
            "notes",
            "comp_links",
            "profit_projection",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "profit_projection", "created_at", "updated_at"]
        extra_kwargs = {"item": {"required": False}}

    def validate(self, data):
        is_overridden = data.get(
            "is_overridden",
            self.instance.is_overridden if self.instance else False,
        )
        override_reason = data.get(
            "override_reason",
            self.instance.override_reason if self.instance else "",
        )
        if is_overridden and not override_reason.strip():
            raise serializers.ValidationError(
                {"override_reason": "Manual overrides require an override reason."}
            )

        score = data.get(
            "confidence_score",
            self.instance.confidence_score if self.instance else None,
        )
        if score is not None and not 0 <= score <= 1:
            raise serializers.ValidationError(
                {"confidence_score": "Confidence score must be between 0 and 1."}
            )
        return data

    def create(self, validated_data):
        with transaction.atomic():
            comp_links_data = validated_data.pop("comp_links", [])
            item = self.context.get("item") or validated_data.get("item")
            if item is None:
                raise serializers.ValidationError({"item": "This field is required."})
            validated_data["item"] = item

            requested_current = validated_data.pop("is_current", False)
            strategy_key = validated_data.get("strategy", ValuationReport.Strategy.COMP_BASED)
            included_comps = self._included_comps(item, comp_links_data)
            self._apply_strategy_defaults(validated_data, strategy_key, included_comps)
            if validated_data.get("fee_schedule") is None:
                validated_data["fee_schedule"] = active_fee_schedule()

            report = ValuationReport.objects.create(is_current=False, **validated_data)
            self._replace_comp_links(report, comp_links_data)
            if requested_current:
                from apps.valuation.services import set_current

                report = set_current(report)
            return report

    def update(self, instance, validated_data):
        with transaction.atomic():
            comp_links_data = validated_data.pop("comp_links", None)
            requested_current = validated_data.pop("is_current", None)
            for field, value in validated_data.items():
                setattr(instance, field, value)
            instance.save()
            if comp_links_data is not None:
                self._replace_comp_links(instance, comp_links_data)
            if requested_current is True:
                from apps.valuation.services import set_current

                instance = set_current(instance)
            elif requested_current is False and instance.is_current:
                instance.is_current = False
                instance.save(update_fields=["is_current", "updated_at"])
            return instance

    def get_profit_projection(self, obj):
        schedule = obj.fee_schedule or active_fee_schedule()
        if schedule is None:
            return []

        true_cost = true_cost_for_item(obj.item)
        rows = []
        for label, price in [
            ("fast_sale", obj.fast_sale_price),
            ("suggested", obj.suggested_price),
            ("patient", obj.patient_price),
        ]:
            if price is None:
                continue
            breakdown = calculate_profit(
                sale_price=price,
                true_cost=true_cost,
                schedule=schedule,
                outbound_shipping=obj.item.est_outbound_shipping,
                packaging=obj.item.est_packaging_cost,
            ).as_serialized()
            breakdown["label"] = label
            rows.append(breakdown)
        return rows

    def _included_comps(self, item, comp_links_data):
        if not comp_links_data:
            return list(item.comparables.filter(price__isnull=False))
        comparable_ids = [
            link["comparable"].id
            for link in comp_links_data
            if link.get("included", True) and link.get("comparable") is not None
        ]
        return list(Comparable.objects.filter(id__in=comparable_ids, item=item))

    def _apply_strategy_defaults(self, validated_data, strategy_key, included_comps):
        inputs = validated_data.get("inputs") or {}
        validated_data["inputs"] = inputs
        if strategy_key in {
            ValuationReport.Strategy.COMMODITY_MANUAL,
            ValuationReport.Strategy.COMMODITY_LIVE,
        }:
            validated_data["currency"] = str(
                inputs.get("currency") or validated_data.get("currency") or "AUD"
            ).upper()

        try:
            strategy = get_strategy(strategy_key)
        except ValueError as exc:
            raise serializers.ValidationError({"strategy": str(exc)}) from exc

        try:
            result = strategy.estimate(
                item=validated_data["item"],
                included_comps=included_comps,
                inputs=inputs,
            )
        except MetalsUnavailable:
            raise
        except (NotImplementedError, ValueError) as exc:
            target = (
                "inputs"
                if strategy_key
                in {
                    ValuationReport.Strategy.COMMODITY_MANUAL,
                    ValuationReport.Strategy.COMMODITY_LIVE,
                }
                else "strategy"
            )
            raise serializers.ValidationError({target: str(exc)}) from exc

        for model_field, result_field in DERIVED_FIELDS.items():
            if validated_data.get(model_field) is None:
                validated_data[model_field] = getattr(result, result_field)

    def _replace_comp_links(self, report, comp_links_data):
        if comp_links_data is None:
            return
        report.comp_links.all().delete()
        for link in comp_links_data:
            comparable = link["comparable"]
            if comparable.item_id != report.item_id:
                raise serializers.ValidationError(
                    {"comp_links": "Comparable does not belong to this item."}
                )
            ValuationComparable.objects.create(
                report=report,
                comparable=comparable,
                included=link.get("included", True),
                exclude_reason=link.get("exclude_reason", ""),
            )
