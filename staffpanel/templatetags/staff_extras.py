from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()

GOOD = {"success", "completed", "approved", "released", "active", "delivered", "paid"}
WARN = {"pending", "awaiting_account", "awaiting_payment", "offered", "paid_held", "paid_escrow", "initialized", "processing", "in_transit",
        "courier_assigned", "accepted", "picked_up", "confirmed"}
BAD = {"needs_attention", "disputed", "rejected", "suspended", "failed", "refund_pending", "cancelled", "refunded", "removed", "sold_out"}


@register.filter
def naira(value):
    try:
        return "₦{:,.2f}".format(Decimal(value))
    except (InvalidOperation, TypeError, ValueError):
        return "₦0.00"


@register.filter
def pill(status):
    s = str(status)
    kind = "good" if s in GOOD else "bad" if s in BAD else "warn" if s in WARN else "plain"
    return kind


@register.filter
def label(status):
    return str(status).replace("_", " ").capitalize()
