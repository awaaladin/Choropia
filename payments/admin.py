from django.contrib import admin

from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("reference", "order", "amount", "status", "auto_released", "paid_at", "released_at")
    list_filter = ("status", "auto_released")
    search_fields = ("reference", "order__id")
    readonly_fields = ("raw_webhook_payload",)
