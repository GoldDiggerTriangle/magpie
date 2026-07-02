from decimal import Decimal

from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="ProfitSetting",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "seller_mode",
                    models.CharField(
                        choices=[
                            ("free_selling", "Free selling"),
                            ("pro_starter", "Pro Starter"),
                            ("pro_other", "Pro Basic or above"),
                            ("legacy_manual", "Legacy / manual"),
                        ],
                        default="free_selling",
                        max_length=24,
                    ),
                ),
                ("pro_other_final_value_pct", models.DecimalField(decimal_places=3, default=Decimal("13.400"), max_digits=6)),
                ("manual_final_value_pct", models.DecimalField(decimal_places=3, default=Decimal("0"), max_digits=6)),
                ("manual_fixed_fee", models.DecimalField(decimal_places=2, default=Decimal("0"), max_digits=8)),
                ("default_flat_profit_target", models.DecimalField(decimal_places=2, default=Decimal("25"), max_digits=10)),
                ("default_roi_pct", models.DecimalField(decimal_places=3, default=Decimal("30"), max_digits=7)),
                (
                    "default_roi_basis",
                    models.CharField(
                        choices=[("all_in_cash", "All-in cash"), ("buy_price", "On buy price")],
                        default="all_in_cash",
                        max_length=20,
                    ),
                ),
                ("maybe_band_pct", models.DecimalField(decimal_places=3, default=Decimal("10"), max_digits=6)),
                ("schema_version", models.PositiveSmallIntegerField(default=1)),
            ],
            options={"ordering": ["-updated_at"]},
        ),
    ]
