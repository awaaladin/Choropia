from decimal import Decimal, InvalidOperation

import re

import re

import re

import re

from django import template
from django.urls import NoReverseMatch, reverse
from django.urls import NoReverseMatch, reverse
from django.urls import NoReverseMatch, reverse
from django.urls import NoReverseMatch, reverse

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


_TARGETS = {
    "order": "staff:order_detail",
    "payout": "staff:payout_detail",
    "driver": "staff:driver_detail",
    "user": "staff:user_detail",
    "message": "staff:contact_detail",
    "application": "staff:storefront_detail",
    "report": "staff:report_detail",
}


@register.filter
def audit_url(target):
    """Turns an activity-log target such as "application 2" into the page for it, so a row can be clicked to preview the item."""
    match = re.match(r"^(\w+) (\d+)$", str(target or "").strip())
    name = _TARGETS.get(match.group(1)) if match else None
    if not name:
        return ""
    try:
        return reverse(name, args=[int(match.group(2))])
    except NoReverseMatch:
        return ""


_TARGETS = {
    "order": "staff:order_detail",
    "payout": "staff:payout_detail",
    "driver": "staff:driver_detail",
    "user": "staff:user_detail",
    "message": "staff:contact_detail",
    "application": "staff:storefront_detail",
    "report": "staff:report_detail",
}


@register.filter
def audit_url(target):
    """Turns an activity-log target such as "application 2" into the page for it, so a row can be clicked to preview the item."""
    match = re.match(r"^(\w+) (\d+)$", str(target or "").strip())
    name = _TARGETS.get(match.group(1)) if match else None
    if not name:
        return ""
    try:
        return reverse(name, args=[int(match.group(2))])
    except NoReverseMatch:
        return ""


_TARGETS = {
    "order": "staff:order_detail",
    "payout": "staff:payout_detail",
    "driver": "staff:driver_detail",
    "user": "staff:user_detail",
    "message": "staff:contact_detail",
    "application": "staff:storefront_detail",
    "report": "staff:report_detail",
}


@register.filter
def audit_url(target):
    """Turns an activity-log target such as "application 2" into the page for it, so a row can be clicked to preview the item."""
    match = re.match(r"^(\w+) (\d+)$", str(target or "").strip())
    name = _TARGETS.get(match.group(1)) if match else None
    if not name:
        return ""
    try:
        return reverse(name, args=[int(match.group(2))])
    except NoReverseMatch:
        return ""


_TARGETS = {
    "order": "staff:order_detail",
    "payout": "staff:payout_detail",
    "driver": "staff:driver_detail",
    "user": "staff:user_detail",
    "message": "staff:contact_detail",
    "application": "staff:storefront_detail",
    "report": "staff:report_detail",
}


@register.filter
def audit_url(target):
    """Turns an activity-log target such as "application 2" into the page for it, so a row can be clicked to preview the item."""
    match = re.match(r"^(\w+) (\d+)$", str(target or "").strip())
    name = _TARGETS.get(match.group(1)) if match else None
    if not name:
        return ""
    try:
        return reverse(name, args=[int(match.group(2))])
    except NoReverseMatch:
        return ""


@register.filter
def initials(value):
    parts = [p for p in str(value or "").replace("@", " ").replace(".", " ").split() if p]
    return ("".join(p[0] for p in parts[:2]) or "?").upper()


@register.filter
def label(status):
    return str(status).replace("_", " ").capitalize()
