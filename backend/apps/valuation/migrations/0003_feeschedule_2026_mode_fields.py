from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("valuation", "0002_metalspotcache"),
    ]

    operations = [
        migrations.AddField(
            model_name="feeschedule",
            name="seller_mode",
            field=models.CharField(
                choices=[
                    ("free_selling", "Free selling"),
                    ("pro_starter", "Pro Starter"),
                    ("pro_other", "Pro Basic or above"),
                    ("legacy_manual", "Legacy / manual"),
                ],
                db_index=True,
                default="legacy_manual",
                max_length=24,
            ),
        ),
        migrations.AddField(
            model_name="feeschedule",
            name="price_basis",
            field=models.CharField(
                default="seller_receives",
                help_text="Canonical basis this schedule expects for sale prices.",
                max_length=24,
            ),
        ),
        migrations.AddField(
            model_name="feeschedule",
            name="buyer_protection_fee_enabled",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="feeschedule",
            name="international_delivery_pct",
            field=models.DecimalField(decimal_places=3, default=0, max_digits=6),
        ),
    ]
