# Generated for Sprint 0.

import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("inventory", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="PhotoAsset",
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
                (
                    "role",
                    models.CharField(
                        choices=[
                            ("main", "Main"),
                            ("front", "Front"),
                            ("back", "Back"),
                            ("detail", "Detail / close-up"),
                            ("before", "Before"),
                            ("after", "After"),
                            ("other", "Other"),
                        ],
                        default="other",
                        max_length=20,
                    ),
                ),
                ("is_main", models.BooleanField(default=False)),
                ("order_index", models.PositiveIntegerField(default=0)),
                ("original_path", models.CharField(max_length=500)),
                ("processed_path", models.CharField(blank=True, default="", max_length=500)),
                ("thumb_path", models.CharField(blank=True, default="", max_length=500)),
                ("width", models.PositiveIntegerField(blank=True, null=True)),
                ("height", models.PositiveIntegerField(blank=True, null=True)),
                ("bytes_original", models.PositiveIntegerField(blank=True, null=True)),
                ("exif_stripped", models.BooleanField(default=False)),
                ("quality_score", models.FloatField(blank=True, null=True)),
                (
                    "item",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="photos",
                        to="inventory.inventoryitem",
                    ),
                ),
            ],
            options={
                "ordering": ["item", "order_index", "created_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="photoasset",
            constraint=models.UniqueConstraint(
                condition=models.Q(("is_main", True)),
                fields=("item",),
                name="one_main_photo_per_item",
            ),
        ),
    ]
