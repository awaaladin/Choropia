from django.db import migrations, models

import common.public_ids


def fill(apps, schema_editor):
    """Give every existing row its own random code (a column default would give them all the same one)."""
    Model = apps.get_model("orders", "Order")
    used = set()
    for row in Model.objects.filter(public_id__isnull=True).only("pk").iterator():
        code = common.public_ids.new_public_id()
        while code in used or Model.objects.filter(public_id=code).exists():
            code = common.public_ids.new_public_id()
        used.add(code)
        Model.objects.filter(pk=row.pk).update(public_id=code)


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0003_alter_order_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="public_id",
            field=models.CharField(max_length=10, null=True, editable=False),
        ),
        migrations.RunPython(fill, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="order",
            name="public_id",
            field=models.CharField(default=common.public_ids.new_public_id, editable=False, max_length=10, unique=True),
        ),
    ]
