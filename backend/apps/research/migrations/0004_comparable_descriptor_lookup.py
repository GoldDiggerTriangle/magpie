from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0001_initial"),
        ("research", "0003_comparable_price_basis"),
    ]

    operations = [
        migrations.AlterField(
            model_name="comparable",
            name="item",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="comparables",
                to="inventory.inventoryitem",
            ),
        ),
        migrations.AddField(
            model_name="comparable",
            name="descriptor_category",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="descriptor_comparables",
                to="catalog.productcategory",
            ),
        ),
        migrations.AddField(
            model_name="comparable",
            name="descriptor_terms",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="comparable",
            name="descriptor_attributes",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddIndex(
            model_name="comparable",
            index=models.Index(fields=["descriptor_category"], name="research_co_descrip_df6eba_idx"),
        ),
    ]
