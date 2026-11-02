"""A once-a-day reminder of everything that is waiting for a person. Runs from the scheduled-jobs endpoint (every few minutes),
sends at most one email per day, and says nothing on days when nothing is waiting."""
from datetime import timedelta

from django.utils import timezone

from dispatch.models import DriverProfile, OrderDelivery
from notifications import staff_alerts
from orders.models import Order
from orders.state_machine import OrderStatus
from payments.models import Payout

from .models import AuditLog

ACTION = "digest.sent"


def send_daily_digest(now=None):
    now = now or timezone.now()
    if AuditLog.objects.filter(action=ACTION, at__gte=now - timedelta(hours=20)).exists():
        return {"sent": False, "reason": "already sent today"}

    old = now - timedelta(hours=24)
    waiting = []
    drivers = DriverProfile.objects.filter(status=DriverProfile.Status.PENDING, documents__isnull=False).distinct().count()
    if drivers:
        waiting.append(f"{drivers} driver application{'s' if drivers != 1 else ''} to review.")
    disputes = Order.objects.filter(status=OrderStatus.DISPUTED).count()
    if disputes:
        waiting.append(f"{disputes} open dispute{'s' if disputes != 1 else ''} to settle.")
    owed = Payout.objects.exclude(status=Payout.Status.SUCCESS).filter(payment__status="released")
    if owed.exists():
        total = sum(p.net_amount for p in owed)
        waiting.append(f"{owed.count()} payout{'s' if owed.count() != 1 else ''} not paid yet, {staff_alerts.money(total)} in all.")
    stuck = OrderDelivery.objects.filter(status=OrderDelivery.Status.OFFERED, offered_at__lte=old).count()
    if stuck:
        waiting.append(f"{stuck} paid delivery job{'s' if stuck != 1 else ''} with no driver for over a day.")
    unsent = Order.objects.filter(status=OrderStatus.PAID_ESCROW, payment__paid_at__lte=now - timedelta(days=3)).count()
    if unsent:
        waiting.append(f"{unsent} paid order{'s' if unsent != 1 else ''} not dispatched by the seller after 3 days (refunded automatically at 7).")

    if not waiting:
        return {"sent": False, "reason": "nothing waiting"}
    staff_alerts.alert("Daily summary: things waiting for you", "Waiting for you", waiting, "/staff/")
    AuditLog.objects.create(action=ACTION, detail="; ".join(waiting)[:300])
    return {"sent": True, "items": len(waiting)}
