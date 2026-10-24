from django.contrib import admin

from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "reference",
        "order",
        "provider",
        "amount",
        "crypto_amount",
        "status",
        "auto_released",
        "paid_at",
        "released_at",
    )
    list_filter = ("provider", "status", "auto_released")
    search_fields = ("reference", "order__id", "paystack_transaction_id", "gaxtron_payment_id", "tx_hash")
    readonly_fields = ("raw_webhook_payload",)
