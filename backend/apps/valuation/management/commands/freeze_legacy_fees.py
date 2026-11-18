import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.valuation.fee_engine import freeze_legacy_copies


class Command(BaseCommand):
    help = "Copy approved pre-engine sale evidence without recalculating it."

    def add_arguments(self, parser):
        parser.add_argument("--manifest", required=True)

    def handle(self, *args, **options):
        try:
            document = json.loads(Path(options["manifest"]).read_text(encoding="utf-8"))
            count = freeze_legacy_copies(document)
        except Exception:
            raise CommandError("Legacy snapshot copy refused; no partial copy retained.") from None
        self.stdout.write(f"Legacy snapshots copied: {count}; no rates or periods created.")
