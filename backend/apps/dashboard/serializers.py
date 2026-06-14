from __future__ import annotations

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.dashboard.models import (
    DEFAULT_KPI_TILES,
    KPI_TILE_CATALOG,
    DashboardPreference,
    sanitize_kpi_tiles,
)


def available_kpi_tiles() -> list[dict]:
    return [
        {"id": tile_id, **definition}
        for tile_id, definition in KPI_TILE_CATALOG.items()
    ]


class DashboardPreferenceSerializer(serializers.ModelSerializer):
    available_tiles = serializers.SerializerMethodField()

    class Meta:
        model = DashboardPreference
        fields = ["kpi_tiles", "schema_version", "available_tiles", "updated_at"]
    read_only_fields = ["schema_version", "available_tiles", "updated_at"]

    def validate_kpi_tiles(self, value):
        try:
            return sanitize_kpi_tiles(list(value or []))
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict["kpi_tiles"]) from exc

    def get_available_tiles(self, obj):
        return available_kpi_tiles()


def default_preference_payload() -> dict:
    return {
        "kpi_tiles": DEFAULT_KPI_TILES,
        "schema_version": 1,
        "available_tiles": available_kpi_tiles(),
        "updated_at": None,
    }
