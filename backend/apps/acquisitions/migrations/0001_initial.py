# Generated for Sprint 0.

import uuid
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="AcquisitionRecord",
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
                ("source", models.CharField(blank=True, default="", max_length=200)),
                ("acquired_on", models.DateField(blank=True, null=True)),
                (
                    "total_cost",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        max_digits=12,
                        null=True,
                    ),
                ),
                ("currency", models.CharField(default="AUD", max_length=3)),
                ("travel_notes", models.TextField(blank=True, default="")),
                ("notes", models.TextField(blank=True, default="")),
            ],
            options={
                "ordering": ["-acquired_on", "-created_at"],
            },
        ),
    ]
