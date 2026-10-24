from django.contrib import admin

from .models import Payment, Payout, PayoutAccount


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


@admin.register(PayoutAccount)
class PayoutAccountAdmin(admin.ModelAdmin):
    list_display = ("user", "bank_name", "account_last4", "account_name", "updated_at")
    search_fields = ("user__email", "account_name")
    readonly_fields = ("recipient_code",)


@admin.register(Payout)
class PayoutAdmin(admin.ModelAdmin):
    list_display = ("id", "payment", "seller", "gross_amount", "commission_amount", "net_amount", "status", "attempts", "created_at")
    list_filter = ("status",)
    search_fields = ("transfer_reference", "payment__reference", "seller__email")
    readonly_fields = (
        "payment", "seller", "gross_amount", "commission_rate", "commission_amount", "net_amount",
        "transfer_reference", "transfer_references", "paystack_transfer_code", "bank_name",
        "account_last4", "account_name", "initiated_at", "completed_at",
    )
