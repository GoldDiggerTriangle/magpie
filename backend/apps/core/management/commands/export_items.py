import csv
import sys

from django.core.management.base import BaseCommand
from django.db.models import Count

from apps.inventory.models import InventoryItem


class Command(BaseCommand):
    help = "Export inventory items to CSV."

    def add_arguments(self, parser):
        parser.add_argument(
            "--csv",
            nargs="?",
            const="-",
            default="-",
            metavar="PATH",
            help="Write CSV to PATH, or stdout when no path is supplied.",
        )

    def handle(self, *args, **options):
        output_path = options["csv"]
        queryset = (
            InventoryItem.objects.select_related("category", "location", "acquisition")
            .annotate(photo_count=Count("photos"))
            .order_by("sku")
        )

        fieldnames = [
            "id",
            "sku",
            "title",
            "category",
            "status",
            "condition",
            "location",
            "acquisition_cost",
            "estimated_value",
            "min_price",
            "target_price",
            "currency",
            "photo_count",
            "created_at",
            "updated_at",
        ]

        if output_path == "-":
            self.write_csv(sys.stdout, fieldnames, queryset)
            return

        with open(output_path, "w", newline="", encoding="utf-8") as handle:
            self.write_csv(handle, fieldnames, queryset)
        self.stdout.write(self.style.SUCCESS(f"Items exported to {output_path}"))

    def write_csv(self, handle, fieldnames, queryset) -> None:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for item in queryset:
            writer.writerow(
                {
                    "id": item.id,
                    "sku": item.sku,
                    "title": item.title,
                    "category": item.category.name if item.category else "",
                    "status": item.status,
                    "condition": item.condition,
                    "location": item.location.label if item.location else "",
                    "acquisition_cost": item.acquisition_cost,
                    "estimated_value": item.estimated_value,
                    "min_price": item.min_price,
                    "target_price": item.target_price,
                    "currency": item.currency,
                    "photo_count": item.photo_count,
                    "created_at": item.created_at,
                    "updated_at": item.updated_at,
                }
            )
