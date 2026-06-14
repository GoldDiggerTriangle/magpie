from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models

from apps.core.models import TimeStampedUUIDModel


DEFAULT_KPI_TILES = [
    "realised_profit",
    "net_proceeds",
    "sell_through",
    "items_sold",
    "avg_realised_margin",
]

KPI_TILE_CATALOG = {
    "realised_profit": {
        "label": "Realised profit",
        "format": "currency",
        "description": "Known-cost sales only.",
    },
    "gross_revenue": {
        "label": "Revenue",
        "format": "currency",
        "description": "Gross sale price, including external sales.",
    },
    "net_proceeds": {
        "label": "Net proceeds",
        "format": "currency",
        "description": "Revenue less fees and shipping.",
    },
    "items_sold": {
        "label": "Items sold",
        "format": "integer",
        "description": "Quantity sold in the filtered period.",
    },
    "sell_through": {
        "label": "Sell-through",
        "format": "percent",
        "description": "Sold units divided by sold plus currently available units.",
    },
    "avg_realised_margin": {
        "label": "Avg margin",
        "format": "percent",
        "description": "Aggregate margin over known-cost sales.",
    },
    "avg_time_to_sale": {
        "label": "Avg time to sale",
        "format": "days",
        "description": "Mean days from acquisition or capture to sale.",
    },
    "inventory_cost_basis": {
        "label": "Inventory cost",
        "format": "currency",
        "description": "Cost basis of currently available inventory.",
    },
    "estimated_inventory_value": {
        "label": "Est. inventory value",
        "format": "currency",
        "description": "Current estimated value of available inventory.",
    },
    "aged_inventory_count": {
        "label": "Aged stock",
        "format": "integer",
        "description": "Available items older than 90 days.",
    },
    "unresolved_ebay_staging_count": {
        "label": "eBay to triage",
        "format": "integer",
        "description": "Pending imported eBay order lines.",
    },
    "cost_basis_unknown_sales_count": {
        "label": "Unknown-cost sales",
        "format": "integer",
        "description": "Sales excluded from profit and margin.",
    },
}

MIN_KPI_TILES = 3
MAX_KPI_TILES = 5


def sanitize_kpi_tiles(tile_ids: list[str], *, reject_below_min: bool = True) -> list[str]:
    seen = set()
    sanitized = []
    for tile_id in tile_ids:
        if tile_id not in KPI_TILE_CATALOG or tile_id in seen:
            continue
        seen.add(tile_id)
        sanitized.append(tile_id)
        if len(sanitized) == MAX_KPI_TILES:
            break

    if reject_below_min and len(sanitized) < MIN_KPI_TILES:
        raise ValidationError(
            {
                "kpi_tiles": (
                    f"Choose at least {MIN_KPI_TILES} recognised KPI tiles."
                )
            }
        )
    return sanitized


class DashboardPreference(TimeStampedUUIDModel):
    kpi_tiles = models.JSONField(default=list, blank=True)
    schema_version = models.PositiveSmallIntegerField(default=1)

    class Meta:
        ordering = ["-updated_at"]

    def clean(self) -> None:
        self.kpi_tiles = sanitize_kpi_tiles(self.kpi_tiles or DEFAULT_KPI_TILES)

    def save(self, *args, **kwargs) -> None:
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return "Dashboard preferences"
