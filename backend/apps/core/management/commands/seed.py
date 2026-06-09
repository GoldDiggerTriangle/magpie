from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils.text import slugify

from apps.catalog.models import ProductCategory
from apps.inventory.models import InventoryItem
from apps.locations.models import StorageLocation


class Command(BaseCommand):
    help = "Seed Sprint 0 categories, locations, and sample inventory items."

    def handle(self, *args, **options):
        categories = self.seed_categories()
        locations = self.seed_locations()
        created_items = self.seed_items(categories, locations)

        self.stdout.write(
            self.style.SUCCESS(
                f"Seed complete: {len(categories)} categories, "
                f"{len(locations)} locations, {created_items} sample items created."
            )
        )

    def seed_categories(self) -> dict[str, ProductCategory]:
        specs = [
            ("Stamps", "STM"),
            ("Coins", "COIN"),
            ("Phones & Electronics", "PH"),
            ("Gold", "GOLD"),
            ("Tools", "TOOL"),
            ("Collectibles", "COL"),
            ("Bulk Lots", "LOT"),
            ("Unknown", "UNK"),
        ]
        categories: dict[str, ProductCategory] = {}
        for name, prefix in specs:
            slug = slugify(name)
            category, _ = ProductCategory.objects.update_or_create(
                slug=slug,
                defaults={
                    "name": name,
                    "sku_prefix": prefix,
                    "profile_key": "",
                    "description": "",
                },
            )
            categories[name] = category
        return categories

    def seed_locations(self) -> dict[str, StorageLocation]:
        shed, _ = StorageLocation.objects.update_or_create(
            label="Main Shed",
            parent=None,
            defaults={"type": StorageLocation.LocationType.SHED, "notes": ""},
        )
        shelf_a, _ = StorageLocation.objects.update_or_create(
            label="Shelf A",
            parent=shed,
            defaults={"type": StorageLocation.LocationType.SHELF, "notes": ""},
        )
        shelf_b, _ = StorageLocation.objects.update_or_create(
            label="Shelf B",
            parent=shed,
            defaults={"type": StorageLocation.LocationType.SHELF, "notes": ""},
        )
        bin_1, _ = StorageLocation.objects.update_or_create(
            label="Bin 1",
            parent=shelf_a,
            defaults={"type": StorageLocation.LocationType.BIN, "notes": ""},
        )
        bin_2, _ = StorageLocation.objects.update_or_create(
            label="Bin 2",
            parent=shelf_b,
            defaults={"type": StorageLocation.LocationType.BIN, "notes": ""},
        )
        return {
            "shed": shed,
            "shelf_a": shelf_a,
            "shelf_b": shelf_b,
            "bin_1": bin_1,
            "bin_2": bin_2,
        }

    def seed_items(
        self,
        categories: dict[str, ProductCategory],
        locations: dict[str, StorageLocation],
    ) -> int:
        specs = [
            {
                "title": "Mixed Australian stamp lot",
                "category": categories["Stamps"],
                "status": InventoryItem.Status.CAPTURED,
                "condition": InventoryItem.Condition.UNGRADED,
                "location": locations["bin_1"],
                "estimated_value": Decimal("25.00"),
                "notes": "Placeholder seed item.",
                "attributes": {"lot_type": "mixed"},
            },
            {
                "title": "Pre-decimal coin needing research",
                "category": categories["Coins"],
                "status": InventoryItem.Status.NEEDS_RESEARCH,
                "condition": InventoryItem.Condition.GOOD,
                "location": locations["shelf_a"],
                "estimated_value": Decimal("60.00"),
                "notes": "Check year and mint mark later.",
                "attributes": {"country": "Australia"},
            },
            {
                "title": "Used smartphone ready to list",
                "category": categories["Phones & Electronics"],
                "status": InventoryItem.Status.READY_TO_LIST,
                "condition": InventoryItem.Condition.GOOD,
                "location": locations["shelf_b"],
                "estimated_value": Decimal("180.00"),
                "notes": "Factory reset before listing.",
                "attributes": {"tested": True},
            },
            {
                "title": "Small gold jewellery parcel",
                "category": categories["Gold"],
                "status": InventoryItem.Status.NEEDS_ID,
                "condition": InventoryItem.Condition.UNGRADED,
                "location": locations["bin_2"],
                "estimated_value": Decimal("350.00"),
                "notes": "Weigh and test in a later sprint.",
                "attributes": {"requires_testing": True},
            },
            {
                "title": "Bulk mixed collectibles box",
                "category": categories["Bulk Lots"],
                "status": InventoryItem.Status.IN_BULK_LOT,
                "condition": InventoryItem.Condition.ACCEPTABLE,
                "location": locations["shed"],
                "estimated_value": Decimal("45.00"),
                "notes": "Split into individual items later.",
                "attributes": {"box_count": 1},
            },
        ]

        created_count = 0
        for spec in specs:
            _, created = InventoryItem.objects.get_or_create(
                title=spec["title"],
                category=spec["category"],
                defaults=spec,
            )
            if created:
                created_count += 1
        return created_count
