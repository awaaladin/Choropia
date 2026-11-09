from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("listings", "0003_listing_campus"),
    ]

    operations = [
        migrations.AddField(
            model_name="listing",
            name="sold_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="listing",
            name="market_visible_until",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddIndex(
            model_name="listing",
            index=models.Index(fields=["status", "market_visible_until"], name="listing_market_visible"),
        ),
    ]
