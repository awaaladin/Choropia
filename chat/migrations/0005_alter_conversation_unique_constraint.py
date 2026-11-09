import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("chat", "0004_message_offer"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="conversation",
            name="user_low",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="direct_threads_low",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="conversation",
            name="user_high",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="direct_threads_high",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="conversation",
            name="orders",
            field=models.ManyToManyField(blank=True, related_name="chat_conversations", to="orders.order"),
        ),
        migrations.AlterField(
            model_name="conversation",
            name="listing",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="conversations",
                to="listings.listing",
            ),
        ),
        migrations.AlterField(
            model_name="message",
            name="message_type",
            field=models.CharField(
                choices=[("text", "Text"), ("offer", "Escrow offer"), ("listing_ref", "Listing reference")],
                default="text",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="message",
            name="listing_snapshot",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="message",
            name="referenced_listing",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="chat_references",
                to="listings.listing",
            ),
        ),
    ]
