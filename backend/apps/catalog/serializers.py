from rest_framework import serializers

from apps.catalog.models import ProductCategory


class ProductCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductCategory
        fields = [
            "id",
            "name",
            "slug",
            "parent",
            "sku_prefix",
            "profile_key",
            "description",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
