# Generated for Sprint 0.

import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="StorageLocation",
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
                ("label", models.CharField(max_length=120)),
                (
                    "type",
                    models.CharField(
                        choices=[
                            ("shed", "Shed"),
                            ("room", "Room"),
                            ("shelf", "Shelf"),
                            ("bin", "Bin"),
                            ("box", "Box"),
                            ("other", "Other"),
                        ],
                        default="box",
                        max_length=20,
                    ),
                ),
                ("notes", models.TextField(blank=True, default="")),
                (
                    "parent",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="children",
                        to="locations.storagelocation",
                    ),
                ),
            ],
            options={
                "ordering": ["label"],
            },
        ),
    ]
