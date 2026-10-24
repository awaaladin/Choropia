from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0002_payment_crypto_amount_payment_crypto_currency_and_more"),
    ]

    operations = [
        # Every payment made before this migration went through Gaxtron.
        migrations.AddField(
            model_name="payment",
            name="provider",
            field=models.CharField(
                choices=[("paystack", "Paystack"), ("gaxtron", "Gaxtron (crypto)")],
                default="gaxtron",
                max_length=20,
            ),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name="payment",
            name="provider",
            field=models.CharField(
                choices=[("paystack", "Paystack"), ("gaxtron", "Gaxtron (crypto)")],
                default="paystack",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="payment",
            name="paystack_transaction_id",
            field=models.CharField(blank=True, max_length=40),
        ),
    ]
