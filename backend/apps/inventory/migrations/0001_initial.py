# Generated for Sprint 0.

import django.contrib.postgres.indexes
import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("acquisitions", "0001_initial"),
        ("catalog", "0001_initial"),
        ("locations", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="InventoryItem",
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
                    "sku",
                    models.CharField(
                        db_index=True,
                        editable=False,
                        max_length=40,
                        unique=True,
                    ),
                ),
                ("title", models.CharField(blank=True, default="", max_length=200)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("captured", "Captured"),
                            ("needs_identification", "Needs identification"),
                            ("needs_cleaning", "Needs cleaning"),
                            ("needs_research", "Needs research"),
                            ("ready_to_list", "Ready to list"),
                            ("listed", "Listed"),
                            ("sold", "Sold"),
                            ("stored", "Stored"),
                            ("archived", "Archived"),
                            ("in_bulk_lot", "Part of bulk lot"),
                        ],
                        default="captured",
                        max_length=30,
                    ),
                ),
                (
                    "condition",
                    models.CharField(
                        choices=[
                            ("new", "New"),
                            ("like_new", "Like new"),
                            ("very_good", "Very good"),
                            ("good", "Good"),
                            ("acceptable", "Acceptable"),
                            ("for_parts", "For parts / not working"),
                            ("ungraded", "Ungraded / unknown"),
                        ],
                        default="ungraded",
                        max_length=20,
                    ),
                ),
                (
                    "acquisition_cost",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        max_digits=12,
                        null=True,
                    ),
                ),
                (
                    "estimated_value",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        max_digits=12,
                        null=True,
                    ),
                ),
                (
                    "min_price",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        max_digits=12,
                        null=True,
                    ),
                ),
                (
                    "target_price",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        max_digits=12,
                        null=True,
                    ),
                ),
                ("currency", models.CharField(default="AUD", max_length=3)),
                ("notes", models.TextField(blank=True, default="")),
                ("attributes", models.JSONField(blank=True, default=dict)),
                (
                    "acquisition",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="items",
                        to="acquisitions.acquisitionrecord",
                    ),
                ),
                (
                    "category",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="items",
                        to="catalog.productcategory",
                    ),
                ),
                (
                    "location",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="items",
                        to="locations.storagelocation",
                    ),
                ),
                (
                    "owner",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="items",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["status"], name="item_status_idx"),
                    models.Index(fields=["category"], name="item_category_idx"),
                    django.contrib.postgres.indexes.GinIndex(
                        fields=["attributes"],
                        name="item_attributes_gin",
                    ),
                ],
            },
        ),
    ]
