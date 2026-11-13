from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("listing", "0003_channellisting")]

    operations = [
        migrations.AlterField(
            model_name="listingdraft",
            name="status",
            field=models.CharField(
                max_length=20,
                default="draft",
                choices=[
                    ("draft", "Draft"), ("ready", "Ready"), ("exported", "Exported"),
                    ("staged", "Staged"), ("published", "Published"),
                    ("publish_failed", "Publish failed"), ("archived", "Archived"),
                    ("publishing", "Publishing"), ("publish_unknown", "Publish outcome unknown"),
                ],
            ),
        ),
    ]
