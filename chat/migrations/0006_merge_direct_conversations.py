from django.db import migrations, models
import django.db.models.deletion

from chat.thread_merge import merge_conversations


def merge_threads(apps, schema_editor):
    merge_conversations(apps)


class Migration(migrations.Migration):

    dependencies = [
        ("chat", "0005_alter_conversation_unique_constraint"),
        ("notifications", "0001_initial"),
        ("offers", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(merge_threads, migrations.RunPython.noop),
        migrations.RemoveConstraint(
            model_name="conversation",
            name="unique_conversation_per_buyer_listing",
        ),
        migrations.AlterField(
            model_name="conversation",
            name="user_low",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="direct_threads_low",
                to="accounts.user",
            ),
        ),
        migrations.AlterField(
            model_name="conversation",
            name="user_high",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="direct_threads_high",
                to="accounts.user",
            ),
        ),
        migrations.AddConstraint(
            model_name="conversation",
            constraint=models.UniqueConstraint(fields=("user_low", "user_high"), name="unique_direct_thread_pair"),
        ),
        migrations.AddConstraint(
            model_name="conversation",
            constraint=models.CheckConstraint(
                check=~models.Q(user_low=models.F("user_high")),
                name="direct_thread_distinct_users",
            ),
        ),
    ]
