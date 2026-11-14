from django.core.management.base import BaseCommand
from apps.ebay.publish_state import recover_stale


class Command(BaseCommand):
    help = "Mark stale publishing attempts unknown locally; never sends an eBay request."

    def handle(self, **options):
        self.stdout.write(f"Stale publishing attempts marked unknown: {recover_stale()}")
