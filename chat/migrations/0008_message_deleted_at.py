from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("chat", "0007_encrypt_message_bodies"),
    ]

    operations = [
        migrations.AddField(
            model_name="message",
            name="deleted_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
