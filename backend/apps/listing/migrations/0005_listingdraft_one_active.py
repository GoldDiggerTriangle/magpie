from django.db import migrations, models

from apps.listing.canonical_check import active_draft_violations, violation_message


def assert_no_active_duplicates(apps, schema_editor):
    # Freeze the exclude-terminal rule: unknown/future statuses must remain active.
    violations = active_draft_violations(
        apps.get_model("listing", "ListingDraft"),
        condition=~models.Q(status__in=["archived", "published"]),
        using=schema_editor.connection.alias,
    )
    if violations:
        raise RuntimeError(violation_message(violations))


class Migration(migrations.Migration):
    dependencies = [("listing", "0004_listingdraft_canonical_statuses")]

    operations = [
        migrations.RunPython(assert_no_active_duplicates, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="listingdraft",
            constraint=models.UniqueConstraint(
                fields=("item", "channel"),
                condition=~models.Q(status__in=["archived", "published"]),
                name="listing_one_active_draft",
            ),
        ),
    ]
