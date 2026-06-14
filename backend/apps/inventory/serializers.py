from decimal import Decimal
from uuid import UUID

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.inventory.models import InventoryItem
from apps.photos.serializers import PhotoAssetSerializer
from integrations.storage import LocalFileStorageAdapter


class InventoryItemListSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    main_thumb_url = serializers.SerializerMethodField()
    quantity_sold = serializers.IntegerField(read_only=True)
    quantity_remaining = serializers.IntegerField(read_only=True)

    class Meta:
        model = InventoryItem
        fields = [
            "id",
            "sku",
            "title",
            "status",
            "condition",
            "category",
            "category_name",
            "quantity_total",
            "quantity_sold",
            "quantity_remaining",
            "estimated_value",
            "currency",
            "main_thumb_url",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "sku",
            "category_name",
            "quantity_sold",
            "quantity_remaining",
            "main_thumb_url",
            "created_at",
        ]

    def get_main_thumb_url(self, obj):
        main_photo = obj.main_photo
        if not main_photo or not main_photo.thumb_path:
            return None
        storage = self.context.get("storage") or LocalFileStorageAdapter()
        return storage.url(main_photo.thumb_path)


class InventoryItemDetailSerializer(serializers.ModelSerializer):
    photos = PhotoAssetSerializer(many=True, read_only=True)
    comps_count = serializers.SerializerMethodField()
    current_valuation = serializers.SerializerMethodField()
    quantity_sold = serializers.IntegerField(read_only=True)
    quantity_remaining = serializers.IntegerField(read_only=True)

    class Meta:
        model = InventoryItem
        fields = "__all__"
        read_only_fields = [
            "id",
            "sku",
            "created_at",
            "updated_at",
            "comps_count",
            "current_valuation",
        ]

    def get_comps_count(self, obj):
        manager = getattr(obj, "comparables", None)
        return manager.count() if manager is not None else 0

    def get_current_valuation(self, obj):
        manager = getattr(obj, "valuation_reports", None)
        if manager is None:
            return None
        report = (
            manager.filter(is_current=True)
            .values(
                "id",
                "strategy",
                "suggested_price",
                "fast_sale_price",
                "patient_price",
                "min_acceptable_price",
                "confidence_score",
                "confidence_reason",
            )
            .first()
        )
        if report is None:
            return None
        return {
            key: (str(value) if isinstance(value, (Decimal, UUID)) else value)
            for key, value in report.items()
        }

    def validate(self, data):
        attrs = dict(data)
        if self.instance:
            for field in [
                "title",
                "category",
                "status",
                "condition",
                "quantity_total",
                "location",
                "acquisition",
                "acquisition_cost",
                "refurb_cost",
                "inbound_shipping_cost",
                "est_outbound_shipping",
                "est_packaging_cost",
                "estimated_value",
                "min_price",
                "target_price",
                "currency",
                "notes",
                "attributes",
                "owner",
            ]:
                if field not in attrs:
                    attrs[field] = getattr(self.instance, field)

        item = InventoryItem(**attrs)
        if self.instance:
            item.pk = self.instance.pk
            item.sku = self.instance.sku

        try:
            item.clean()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict) from exc

        quantity_total = data.get(
            "quantity_total",
            self.instance.quantity_total if self.instance else 1,
        )
        if self.instance and quantity_total < self.instance.quantity_sold:
            raise serializers.ValidationError(
                {
                    "quantity_total": (
                        "Quantity total cannot be lower than active sold quantity."
                    )
                }
            )

        data["attributes"] = item.attributes
        return data
