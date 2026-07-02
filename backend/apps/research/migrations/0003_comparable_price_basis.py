from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("research", "0002_comparable_grade_comparable_match_reason_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="comparable",
            name="price_basis",
            field=models.CharField(
                choices=[
                    ("buyer_visible", "Buyer-visible total"),
                    ("seller_receives", "Seller receives"),
                    ("unknown", "Unknown / review"),
                ],
                db_index=True,
                default="unknown",
                max_length=24,
            ),
        ),
    ]
