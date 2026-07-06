from decimal import Decimal
from datetime import date

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.text import slugify

from apps.catalog.models import ProductCategory
from apps.inventory.models import InventoryItem
from apps.listing.models import ListingBoilerplate, ListingDraft
from apps.listing.views import create_generated_draft
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
        self.seed_listing(items)

        self.stdout.write(
            self.style.SUCCESS(
                f"Seed complete: {len(categories)} categories, "
                f"{len(locations)} locations, {created_items} sample items created."
            )
        )

    def seed_categories(self) -> dict[str, ProductCategory]:
        specs = [
            ("Stamps", "STM", "stamps"),
            ("Coins", "COIN", "coins"),
            ("Banknotes", "NOTE", "banknotes"),
            ("Phones & Electronics", "PH", "phones"),
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
                "title": "Seed/example stamp - Australia 1932 Sydney Harbour Bridge 2d",
                "legacy_titles": ["Mixed Australian stamp lot"],
                "category": categories["Stamps"],
                "status": InventoryItem.Status.CAPTURED,
                "condition": InventoryItem.Condition.UNGRADED,
                "location": locations["bin_1"],
                "estimated_value": Decimal("25.00"),
                "notes": "Seed/example stamp data; catalogue reference is illustrative, not authoritative.",
                "attributes": {
                    "country": "Australia",
                    "year": 1932,
                    "denomination": "2d",
                    "face_value_currency": "AUD (pre-decimal d)",
                    "catalogue_refs": [{"system": "SG", "number": "144"}],
                    "mint_used": "used",
                    "topic_theme": "bridges",
                },
            },
            {
                "title": "Seed/example coin - 1937 Australian Crown",
                "legacy_titles": ["Pre-decimal coin needing research"],
                "category": categories["Coins"],
                "status": InventoryItem.Status.NEEDS_RESEARCH,
                "condition": InventoryItem.Condition.GOOD,
                "location": locations["shelf_a"],
                "estimated_value": Decimal("60.00"),
                "notes": "Seed/example numismatic coin data.",
                "attributes": {
                    "country": "Australia",
                    "year": 1937,
                    "denomination": "Crown",
                    "ruler_or_reign": "George VI",
                    "grade": "VF",
                    "catalogue_refs": [{"system": "KM", "number": "34"}],
                    "mintage": 1008000,
                },
            },
            {
                "title": "Seed/example bullion coin - George V sovereign",
                "category": categories["Coins"],
                "status": InventoryItem.Status.NEEDS_RESEARCH,
                "condition": InventoryItem.Condition.UNGRADED,
                "location": locations["bin_2"],
                "estimated_value": Decimal("850.00"),
                "notes": "Seed/example bullion sovereign; commodity valuation uses manual fake inputs.",
                "attributes": {
                    "country": "United Kingdom",
                    "denomination": "Sovereign",
                    "ruler_or_reign": "George V",
                    "composition": "22ct gold",
                    "weight_g": "7.988",
                    "fineness": "0.9167",
                },
            },
            {
                "title": "Seed/example phone - Samsung Galaxy S21",
                "legacy_titles": ["Used smartphone ready to list"],
                "category": categories["Phones & Electronics"],
                "status": InventoryItem.Status.READY_TO_LIST,
                "condition": InventoryItem.Condition.GOOD,
                "location": locations["shelf_b"],
                "estimated_value": Decimal("180.00"),
                "notes": "Factory reset before listing. Seed/example phone data.",
                "attributes": {
                    "brand": "Samsung",
                    "model": "Galaxy S21",
                    "storage_gb": 128,
                    "ram_gb": 8,
                    "network_status": "unlocked",
                    "battery_health_pct": 87,
                    "faults": "light scratch rear glass",
                },
            },
            {
                "title": "Small gold jewellery parcel",
                "category": categories["Gold"],
                "status": InventoryItem.Status.NEEDS_ID,
                "condition": InventoryItem.Condition.UNGRADED,
                "location": locations["bin_2"],
                "estimated_value": Decimal("350.00"),
                "notes": "Seed gold item with fake commodity fields.",
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
            legacy_titles = spec.pop("legacy_titles", [])
            lookup_titles = [spec["title"], *legacy_titles]
            item = (
                InventoryItem.objects.filter(
                    title__in=lookup_titles,
                    category=spec["category"],
                )
                .order_by("created_at")
                .first()
            )
            created = item is None
            if item is None:
                item = InventoryItem(**spec)
            else:
                for field, value in spec.items():
                    setattr(item, field, value)
            item.full_clean()
            item.save()
            items[spec["title"]] = item
            if created:
                created_count += 1
        return items, created_count

    def seed_fee_schedule(self) -> FeeSchedule:
        schedule, _ = FeeSchedule.objects.update_or_create(
            name="eBay AU 2026 free selling",
            effective_from=date(2026, 1, 1),
            defaults={
                "is_active": True,
                "seller_mode": FeeSchedule.SellerMode.FREE_SELLING,
                "price_basis": "seller_receives",
                "buyer_protection_fee_enabled": True,
                "international_delivery_pct": Decimal("3.000"),
                "final_value_pct": Decimal("0.000"),
                "per_order_fee": Decimal("0.00"),
                "promoted_pct": Decimal("0.000"),
                "gst_pct": Decimal("0.000"),
                "default_packaging_cost": Decimal("1.50"),
                "default_outbound_shipping": Decimal("12.00"),
                "notes": (
                    "Sprint 18 eBay AU 2026 free-selling model: seller FVF is zero; "
                    "Buyer Protection Fee is paid by buyer and normalised separately."
                ),
            },
        )
        return schedule

    def seed_research_and_valuations(
        self,
        items: dict[str, InventoryItem],
        fee_schedule: FeeSchedule,
    ) -> None:
        coin = items["Seed/example coin - 1937 Australian Crown"]
        sovereign = items["Seed/example bullion coin - George V sovereign"]
        gold = items["Small gold jewellery parcel"]
        phone = items["Seed/example phone - Samsung Galaxy S21"]

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

        phone_report, _ = ValuationReport.objects.update_or_create(
            item=phone,
            strategy=ValuationReport.Strategy.COMP_BASED,
            notes="Seed phone valuation report for listing draft defaults",
            defaults={
                "fee_schedule": fee_schedule,
                "estimate_low": Decimal("150.00"),
                "estimate_median": Decimal("180.00"),
                "estimate_high": Decimal("220.00"),
                "suggested_price": Decimal("199.00"),
                "fast_sale_price": Decimal("165.00"),
                "patient_price": Decimal("220.00"),
                "min_acceptable_price": Decimal("145.00"),
                "currency": "AUD",
                "confidence_score": 0.55,
                "confidence_reason": "Seed placeholder valuation for UI testing.",
                "is_overridden": False,
                "override_reason": "",
                "inputs": {},
                "is_current": False,
            },
        )
        set_current(phone_report)

        sovereign_inputs = {
            "metal": "gold",
            "weight_g": "7.988",
            "fineness": "0.9167",
            "spot_price_per_g": "105.00",
            "buy_margin_pct": "8.0",
        }
        sovereign_result = get_strategy(
            ValuationReport.Strategy.COMMODITY_MANUAL
        ).estimate(
            item=sovereign,
            included_comps=[],
            inputs=sovereign_inputs,
        )
        sovereign_report, _ = ValuationReport.objects.update_or_create(
            item=sovereign,
            strategy=ValuationReport.Strategy.COMMODITY_MANUAL,
            notes="Seed commodity-manual valuation report for bullion sovereign",
            defaults={
                "fee_schedule": fee_schedule,
                "estimate_low": sovereign_result.low,
                "estimate_median": sovereign_result.median,
                "estimate_high": sovereign_result.high,
                "suggested_price": sovereign_result.suggested,
                "fast_sale_price": sovereign_result.fast_sale,
                "patient_price": sovereign_result.patient,
                "min_acceptable_price": sovereign_result.fast_sale,
                "currency": "AUD",
                "confidence_score": 0.5,
                "confidence_reason": "Seed manual commodity inputs for a coin-category bullion example.",
                "is_overridden": False,
                "override_reason": "",
                "inputs": sovereign_inputs,
                "is_current": False,
            },
        )
        set_current(sovereign_report)

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

    def seed_listing(self, items: dict[str, InventoryItem]) -> None:
        # Placeholder wording only. Replace with Regan's real postage, returns,
        # and payment wording in Django admin before relying on exports.
        ListingBoilerplate.objects.update_or_create(
            channel="ebay_au",
            name="eBay AU — PLACEHOLDER boilerplate",
            defaults={
                "is_active": True,
                "body_html": (
                    "<h2>Postage, returns and payment</h2>"
                    "<p>PLACEHOLDER wording: confirm postage, returns, and payment "
                    "terms in eBay before listing. No external links are included.</p>"
                ),
                "notes": "Placeholder seed boilerplate; edit in admin.",
            },
        )

        phone = items["Seed/example phone - Samsung Galaxy S21"]
        if not ListingDraft.objects.filter(item=phone).exists():
            create_generated_draft(phone)
