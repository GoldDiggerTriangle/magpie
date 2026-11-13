import json

from django.core.management.base import BaseCommand, CommandError
from django.db import connections

from apps.listing.canonical_check import CONSTRAINT_NAME, active_draft_violations, violation_message
from apps.listing.draft_status import active_draft_filter
from apps.listing.models import ListingDraft


class Command(BaseCommand):
    help = "Read-only Migration B pre-check. Names duplicate active drafts; never installs the constraint."
    requires_migrations_checks = False

    def add_arguments(self, parser):
        parser.add_argument("--database", default="default", choices=tuple(connections))

    def handle(self, *args, **options):
        alias = options["database"]
        connection = connections[alias]
        violations = active_draft_violations(
            ListingDraft, condition=active_draft_filter(), using=alias,
        )
        with connection.cursor() as cursor:
            constraints = connection.introspection.get_constraints(cursor, ListingDraft._meta.db_table)
        self.stdout.write(json.dumps({
            "violation_count": len(violations), "violations": violations,
            "constraint_installed": CONSTRAINT_NAME in constraints,
        }, sort_keys=True))
        if violations:
            raise CommandError(violation_message(violations))
