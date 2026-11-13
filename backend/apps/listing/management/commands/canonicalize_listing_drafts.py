import json

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from apps.listing.canonical import apply_migration_a, migration_a_plan


class Command(BaseCommand):
    help = "Migration A: report canonical keepers, or archive approved non-keepers locally. Never calls eBay."
    requires_migrations_checks = False

    def add_arguments(self, parser):
        mode = parser.add_mutually_exclusive_group()
        mode.add_argument("--dry-run", action="store_true", help="Read-only report (the default).")
        mode.add_argument("--apply", action="store_true", help="Apply an owner-approved report.")
        parser.add_argument("--approved-fingerprint", default="", help="Fingerprint from the approved dry run; required with --apply.")

    def handle(self, *args, **options):
        if options["apply"] and not options["approved_fingerprint"]:
            raise CommandError("--apply requires --approved-fingerprint from an owner-approved dry run.")
        try:
            plan = apply_migration_a(options["approved_fingerprint"]) if options["apply"] else migration_a_plan()
        except ValidationError:
            raise CommandError("Approval no longer matches current drafts; run a fresh dry run.") from None
        self.stdout.write(json.dumps({"mode": "apply" if options["apply"] else "dry_run", **plan}, sort_keys=True))
