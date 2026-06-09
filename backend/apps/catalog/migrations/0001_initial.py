# Generated for Sprint 0.

import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="ProductCategory",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=120)),
                ("slug", models.SlugField(max_length=140, unique=True)),
                ("sku_prefix", models.CharField(default="GSP", max_length=12)),
                ("profile_key", models.CharField(blank=True, default="", max_length=60)),
                ("description", models.TextField(blank=True, default="")),
                (
                    "parent",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="children",
                        to="catalog.productcategory",
                    ),
                ),
            ],
            options={
                "verbose_name_plural": "product categories",
                "ordering": ["name"],
            },
        ),
    ]
