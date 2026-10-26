from django.contrib import admin, messages
from django.db import transaction

from .models import Order, OrderStatusHistory
from .state_machine import InvalidOrderTransition, OrderStatus


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
    actions = ["resolve_refund_buyer", "resolve_release_to_seller"]

    def _resolve(self, request, queryset, refund):
        from payments.paystack import PaystackError
        from payments.services import refund_escrow, release_escrow

        done = 0
        for order in queryset.filter(status=OrderStatus.DISPUTED):
            try:
                with transaction.atomic():
                    if refund:
                        order.transition_to(OrderStatus.REFUNDED, actor=request.user, note="Dispute resolved: buyer refunded (admin)")
                        refund_escrow(order)
                    else:
                        order.transition_to(OrderStatus.COMPLETED, actor=request.user, note="Dispute resolved: seller paid (admin)")
                        release_escrow(order, auto=False)
                done += 1
            except (PaystackError, InvalidOrderTransition, ValueError) as exc:
                self.message_user(request, f"Order #{order.pk} was not changed: {exc}", level=messages.ERROR)
        self.message_user(request, f"{done} disputed order(s) resolved.", level=messages.SUCCESS if done else messages.WARNING)

    @admin.action(description="Resolve DISPUTED orders: refund the buyer (real Paystack refund)")
    def resolve_refund_buyer(self, request, queryset):
        self._resolve(request, queryset, refund=True)

    @admin.action(description="Resolve DISPUTED orders: pay the seller (release escrow)")
    def resolve_release_to_seller(self, request, queryset):
        self._resolve(request, queryset, refund=False)
