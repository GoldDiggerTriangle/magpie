from django.db import migrations


def add_banknotes_category(apps, schema_editor):
    ProductCategory = apps.get_model("catalog", "ProductCategory")
    ProductCategory.objects.update_or_create(
        slug="banknotes",
        defaults={
            "name": "Banknotes",
            "sku_prefix": "NOTE",
            "profile_key": "banknotes",
            "description": "",
            "parent": None,
        },
    )


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0002_set_gold_profile_key"),
    ]

    operations = [
        migrations.RunPython(add_banknotes_category, migrations.RunPython.noop),
    ]
