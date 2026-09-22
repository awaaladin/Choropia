from django.contrib import admin

from .models import Order, OrderStatusHistory


class OrderStatusHistoryInline(admin.TabularInline):
    model = OrderStatusHistory
    extra = 0
    readonly_fields = ("from_status", "to_status", "actor", "note", "created_at")
    can_delete = False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "listing", "buyer", "seller", "price", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("listing__title", "buyer__email", "seller__email")
    inlines = [OrderStatusHistoryInline]
