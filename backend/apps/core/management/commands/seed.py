from decimal import Decimal
from datetime import date

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.text import slugify

from apps.catalog.models import ProductCategory
from apps.inventory.models import InventoryItem
from apps.locations.models import StorageLocation
from apps.research.models import Comparable
from apps.valuation.models import (
    FeeSchedule,
    MetalSpotCache,
    ValuationComparable,
    ValuationReport,
)
from apps.valuation.services import set_current
from apps.valuation.strategies import get_strategy


class Command(BaseCommand):
    help = "Seed Sprint 0 categories, locations, and sample inventory items."

    def handle(self, *args, **options):
        categories = self.seed_categories()
        locations = self.seed_locations()
        items, created_items = self.seed_items(categories, locations)
        fee_schedule = self.seed_fee_schedule()
        self.seed_research_and_valuations(items, fee_schedule)

        self.stdout.write(
            self.style.SUCCESS(
                f"Seed complete: {len(categories)} categories, "
                f"{len(locations)} locations, {created_items} sample items created."
            )
        )

    def seed_categories(self) -> dict[str, ProductCategory]:
        specs = [
            ("Stamps", "STM", ""),
            ("Coins", "COIN", ""),
            ("Phones & Electronics", "PH", ""),
            ("Gold", "GOLD", "gold"),
            ("Tools", "TOOL", ""),
            ("Collectibles", "COL", ""),
            ("Bulk Lots", "LOT", ""),
            ("Unknown", "UNK", ""),
        ]
        categories: dict[str, ProductCategory] = {}
        for name, prefix, profile_key in specs:
            slug = slugify(name)
            category, _ = ProductCategory.objects.update_or_create(
                slug=slug,
                defaults={
                    "name": name,
                    "sku_prefix": prefix,
                    "profile_key": profile_key,
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
    ) -> tuple[dict[str, InventoryItem], int]:
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
                "notes": "Seed gold item with fake Sprint 3 commodity fields.",
                "attributes": {
                    "metal": "gold",
                    "weight_g": "8.5",
                    "fineness": "0.375",
                    "form": "jewellery",
                },
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
        items: dict[str, InventoryItem] = {}
        for spec in specs:
            item, created = InventoryItem.objects.update_or_create(
                title=spec["title"],
                category=spec["category"],
                defaults=spec,
            )
            items[spec["title"]] = item
            if created:
                created_count += 1
        return items, created_count

    def seed_fee_schedule(self) -> FeeSchedule:
        # Placeholder rates are not verified eBay rates. Regan must edit this
        # schedule in Django admin before relying on profit calculations.
        schedule, _ = FeeSchedule.objects.update_or_create(
            name="eBay AU (placeholder)",
            effective_from=date(2026, 1, 1),
            defaults={
                "is_active": True,
                "final_value_pct": Decimal("13.400"),
                "per_order_fee": Decimal("0.30"),
                "promoted_pct": Decimal("2.000"),
                "gst_pct": Decimal("10.000"),
                "default_packaging_cost": Decimal("1.50"),
                "default_outbound_shipping": Decimal("12.00"),
                "notes": "Placeholder seed schedule; verify and edit before use.",
            },
        )
        return schedule

    def seed_research_and_valuations(
        self,
        items: dict[str, InventoryItem],
        fee_schedule: FeeSchedule,
    ) -> None:
        coin = items["Pre-decimal coin needing research"]
        gold = items["Small gold jewellery parcel"]

        comp_specs = [
            {
                "item": coin,
                "kind": Comparable.Kind.SOLD,
                "source": "Manual Terapeak note",
                "title": "Similar pre-decimal coin sold example 1",
                "price": Decimal("72.00"),
                "shipping": Decimal("5.00"),
                "observed_on": date(2026, 5, 20),
                "notes": "Human-entered placeholder comp.",
            },
            {
                "item": coin,
                "kind": Comparable.Kind.SOLD,
                "source": "Manual Terapeak note",
                "title": "Similar pre-decimal coin sold example 2",
                "price": Decimal("88.00"),
                "shipping": Decimal("0.00"),
                "observed_on": date(2026, 5, 22),
                "notes": "Human-entered placeholder comp.",
            },
            {
                "item": coin,
                "kind": Comparable.Kind.ACTIVE,
                "source": "eBay AU public search",
                "title": "Active pre-decimal coin asking example",
                "price": Decimal("110.00"),
                "shipping": Decimal("8.00"),
                "observed_on": date(2026, 5, 24),
                "notes": "Active asking price; excluded from seed valuation.",
            },
            {
                "item": coin,
                "kind": Comparable.Kind.DEALER,
                "source": "Dealer list",
                "title": "Dealer asking reference",
                "price": Decimal("125.00"),
                "shipping": None,
                "observed_on": date(2026, 5, 25),
                "notes": "Dealer asking price only.",
            },
        ]
        comparables = []
        for spec in comp_specs:
            comp, _ = Comparable.objects.update_or_create(
                item=spec["item"],
                kind=spec["kind"],
                source=spec["source"],
                title=spec["title"],
                defaults={
                    "price": spec["price"],
                    "shipping": spec["shipping"],
                    "currency": "AUD",
                    "condition": "good",
                    "url": "",
                    "observed_on": spec["observed_on"],
                    "notes": spec["notes"],
                },
            )
            comparables.append(comp)

        included = comparables[:2]
        result = get_strategy(ValuationReport.Strategy.COMP_BASED).estimate(
            item=coin,
            included_comps=included,
            inputs={},
        )
        comp_report, _ = ValuationReport.objects.update_or_create(
            item=coin,
            strategy=ValuationReport.Strategy.COMP_BASED,
            notes="Seed comp-based valuation report",
            defaults={
                "fee_schedule": fee_schedule,
                "estimate_low": result.low,
                "estimate_median": result.median,
                "estimate_high": result.high,
                "suggested_price": result.suggested,
                "fast_sale_price": result.fast_sale,
                "patient_price": result.patient,
                "min_acceptable_price": Decimal("45.00"),
                "currency": "AUD",
                "confidence_score": 0.6,
                "confidence_reason": "Seed comps are placeholders for UI testing.",
                "is_overridden": False,
                "override_reason": "",
                "inputs": {},
                "is_current": False,
            },
        )
        for comp in comparables:
            included_flag = comp in included
            ValuationComparable.objects.update_or_create(
                report=comp_report,
                comparable=comp,
                defaults={
                    "included": included_flag,
                    "exclude_reason": "" if included_flag else "Seed example excluded by human review.",
                },
            )
        set_current(comp_report)

        gold_inputs = {
            "metal": "gold",
            "weight_g": "8.5",
            "fineness": "0.375",
            "spot_price_per_g": "105.00",
            "buy_margin_pct": "8.0",
        }
        gold_result = get_strategy(ValuationReport.Strategy.COMMODITY_MANUAL).estimate(
            item=gold,
            included_comps=[],
            inputs=gold_inputs,
        )
        gold_report, _ = ValuationReport.objects.update_or_create(
            item=gold,
            strategy=ValuationReport.Strategy.COMMODITY_MANUAL,
            notes="Seed commodity-manual valuation report",
            defaults={
                "fee_schedule": fee_schedule,
                "estimate_low": gold_result.low,
                "estimate_median": gold_result.median,
                "estimate_high": gold_result.high,
                "suggested_price": gold_result.suggested,
                "fast_sale_price": gold_result.fast_sale,
                "patient_price": gold_result.patient,
                "min_acceptable_price": gold_result.fast_sale,
                "currency": "AUD",
                "confidence_score": 0.5,
                "confidence_reason": "Seed manual commodity inputs.",
                "is_overridden": False,
                "override_reason": "",
                "inputs": gold_inputs,
                "is_current": False,
            },
        )
        set_current(gold_report)

        now = timezone.now()
        MetalSpotCache.objects.update_or_create(
            metal="gold",
            currency="AUD",
            provider="seed-fake",
            defaults={
                "price_per_gram": Decimal("100.000000"),
                "provider_price": Decimal("3110.347680"),
                "provider_units": "AUD/troy_oz",
                "as_of": now,
                "fetched_at": now,
            },
        )
        live_intrinsic = Decimal("318.75")
        live_inputs = {
            "metal": "gold",
            "currency": "AUD",
            "normalized_price_per_g": "100.000000",
            "provider_price": "3110.347680",
            "provider_units": "AUD/troy_oz",
            "source": "seed-fake",
            "as_of": now.isoformat(),
            "fetched_at": now.isoformat(),
            "cache_hit": False,
            "weight_g": "8.5",
            "fineness": "0.375",
            "calculated_intrinsic_value": str(live_intrinsic),
            "buy_margin_pct": "8.0",
        }
        ValuationReport.objects.update_or_create(
            item=gold,
            strategy=ValuationReport.Strategy.COMMODITY_LIVE,
            notes="Seed fake commodity-live valuation report; no real provider call.",
            defaults={
                "fee_schedule": fee_schedule,
                "estimate_low": live_intrinsic,
                "estimate_median": live_intrinsic,
                "estimate_high": live_intrinsic,
                "suggested_price": live_intrinsic,
                "fast_sale_price": Decimal("293.25"),
                "patient_price": live_intrinsic,
                "min_acceptable_price": Decimal("293.25"),
                "currency": "AUD",
                "confidence_score": 0.5,
                "confidence_reason": "Seed fake live metals quote for UI testing.",
                "is_overridden": False,
                "override_reason": "",
                "inputs": live_inputs,
                "is_current": False,
            },
        )
