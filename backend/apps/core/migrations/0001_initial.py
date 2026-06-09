# Generated for Sprint 0.

from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="SkuSequence",
            fields=[
                ("prefix", models.CharField(max_length=12, primary_key=True, serialize=False)),
                ("last_value", models.PositiveIntegerField(default=0)),
            ],
            options={
                "ordering": ["prefix"],
            },
        ),
    ]
