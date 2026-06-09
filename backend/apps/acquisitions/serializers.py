from rest_framework import serializers

from apps.acquisitions.models import AcquisitionRecord


class AcquisitionRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = AcquisitionRecord
        fields = [
            "id",
            "source",
            "acquired_on",
            "total_cost",
            "currency",
            "travel_notes",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
