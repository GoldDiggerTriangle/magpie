from importlib import import_module

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Read-only pre-check for ChannelListing identity constraints."

    def handle(self, **options):
        check = import_module("apps.listing.migrations.0007_reviewed_publish_protocol").identity_plan
        try:
            rows = check(apps, "default")
        except RuntimeError as exc:
            raise CommandError(str(exc)) from None
        self.stdout.write(f"ChannelListing identity violations: 0; rows checked: {len(rows)}")
