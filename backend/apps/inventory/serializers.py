from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.inventory.models import InventoryItem
from apps.photos.serializers import PhotoAssetSerializer
from integrations.storage import LocalFileStorageAdapter


class InventoryItemListSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    main_thumb_url = serializers.SerializerMethodField()

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
            "estimated_value",
            "currency",
            "main_thumb_url",
            "created_at",
        ]
        read_only_fields = ["id", "sku", "category_name", "main_thumb_url", "created_at"]

    def get_main_thumb_url(self, obj):
        main_photo = obj.main_photo
        if not main_photo or not main_photo.thumb_path:
            return None
        storage = self.context.get("storage") or LocalFileStorageAdapter()
        return storage.url(main_photo.thumb_path)


class InventoryItemDetailSerializer(serializers.ModelSerializer):
    photos = PhotoAssetSerializer(many=True, read_only=True)

    class Meta:
        model = InventoryItem
        fields = "__all__"
        read_only_fields = ["id", "sku", "created_at", "updated_at"]

    def validate(self, data):
        attrs = dict(data)
        if self.instance:
            for field in [
                "title",
                "category",
                "status",
                "condition",
                "location",
                "acquisition",
                "acquisition_cost",
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

        data["attributes"] = item.attributes
        return data
