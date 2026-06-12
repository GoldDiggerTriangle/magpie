from django.core.management.base import BaseCommand, CommandError

from apps.ebay.services import create_merchant_location


class Command(BaseCommand):
    help = "Create the one-time eBay merchant location for the configured environment."

    def add_arguments(self, parser):
        parser.add_argument("--key", required=True, help="Seller-defined merchant location key.")
        parser.add_argument("--name", required=True, help="Human-readable location name.")
        parser.add_argument("--country", required=True, help="Two-letter country code.")
        parser.add_argument("--postal-code", default="", help="Postal code.")
        parser.add_argument("--city", default="", help="City.")
        parser.add_argument("--state", default="", help="State or province.")

    def handle(self, *args, **options):
        if not (options["postal_code"] or (options["city"] and options["state"])):
            raise CommandError("Provide postal-code or both city and state.")
        location = create_merchant_location(
            merchant_location_key=options["key"],
            name=options["name"],
            country=options["country"],
            postal_code=options["postal_code"],
            city=options["city"],
            state=options["state"],
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Merchant location ready: {location.environment} {location.merchant_location_key}"
            )
        )
