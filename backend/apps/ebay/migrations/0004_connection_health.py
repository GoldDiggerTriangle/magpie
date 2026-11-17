import uuid

from django.db import migrations, models
import apps.ebay.health_schema


class Migration(migrations.Migration):
    dependencies = [("ebay", "0003_ebayordersyncstate_ebayorderduplicatecandidate_and_more")]

    operations = [migrations.CreateModel(
        name="EbayConnectionHealth",
        fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("updated_at", models.DateTimeField(auto_now=True)),
            ("environment", models.CharField(max_length=12, choices=[("production", "Production"), ("sandbox", "Sandbox")])),
            ("principal", models.CharField(max_length=12, choices=[("seller", "Seller"), ("application", "Application")])),
            ("connection_id", models.UUIDField(default=uuid.uuid4, editable=False)),
            ("revision", models.PositiveBigIntegerField(default=0)),
            ("operations", models.JSONField(default=dict, blank=True, validators=[apps.ebay.health_schema.validate_operations])),
            ("check_id", models.UUIDField(null=True, blank=True)),
            ("check_started_at", models.DateTimeField(null=True, blank=True)),
            ("check_completed_at", models.DateTimeField(null=True, blank=True)),
            ("next_check_at", models.DateTimeField(null=True, blank=True)),
        ],
        options={"constraints": [models.UniqueConstraint(fields=["environment", "principal"], name="one_connection_health_per_principal")]},
    )]
