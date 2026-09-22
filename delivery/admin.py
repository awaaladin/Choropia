from django.contrib import admin

from .models import Delivery


@admin.register(Delivery)
class DeliveryAdmin(admin.ModelAdmin):
    list_display = ("tracking_id", "order", "provider_name", "status", "created_at")
    list_filter = ("status", "provider_name")
    search_fields = ("tracking_id", "order__id")
