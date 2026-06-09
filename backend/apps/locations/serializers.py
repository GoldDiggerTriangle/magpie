from rest_framework import serializers

from apps.locations.models import StorageLocation


class StorageLocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = StorageLocation
        fields = [
            "id",
            "label",
            "type",
            "parent",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
