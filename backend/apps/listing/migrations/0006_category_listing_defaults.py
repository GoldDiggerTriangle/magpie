import uuid

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("listing", "0005_listingdraft_one_active"), ("catalog", "0003_add_banknotes_category")]
    operations = [
        migrations.CreateModel(
            name="CategoryListingDefaults",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("environment", models.CharField(max_length=12)),
                ("marketplace", models.CharField(default="EBAY_AU", max_length=20)),
                ("values", models.JSONField(blank=True, default=dict)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("category", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="listing_defaults", to="catalog.productcategory")),
            ],
            options={"constraints": [models.UniqueConstraint(fields=("category", "environment", "marketplace"), name="one_listing_default_category")]},
        ),
        migrations.AlterField(model_name="listingdraft", name="listing_format", field=models.CharField(blank=True, choices=[("fixed", "Fixed price"), ("auction", "Auction")], default="fixed", max_length=10)),
    ]
