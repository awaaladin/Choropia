import logging

from celery import shared_task
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from orders.models import Order
from orders.state_machine import InvalidOrderTransition, OrderStatus

from .gaxtron import GaxtronClient, GaxtronError
from .models import Payment
from .services import confirm_payment, release_escrow

logger = logging.getLogger(__name__)


@shared_task
def poll_gaxtron_payments_task():
    """Gaxtron's SSRF guard blocks webhook callbacks to localhost/private hosts, so a
    locally-hosted Choropia can never receive them, and a production one can't rely on a single
    delivery attempt either. This polls gaxtron directly (see gaxtron.py) for every payment
    still waiting on-chain confirmation, and is the only confirmation path dev actually uses."""
    client = GaxtronClient()
    pending = Payment.objects.filter(status=Payment.Status.INITIALIZED).exclude(gaxtron_payment_id__isnull=True)

    confirmed, failed = [], []
    for payment in pending:
        try:
            data = client.get_payment_status(str(payment.gaxtron_payment_id))
        except GaxtronError:
            logger.warning("Gaxtron status check failed for payment %s", payment.id)
            continue

        if data.get("status") == "confirmed":
            confirm_payment(payment.gaxtron_payment_id, tx_hash=data.get("tx_hash"), raw_payload=data)
            confirmed.append(payment.id)
        elif data.get("status") == "failed":
            payment.status = Payment.Status.FAILED
            payment.save(update_fields=["status"])
            failed.append(payment.id)

    return {"confirmed": confirmed, "failed": failed}


@shared_task
def auto_release_escrow_task():
    """Runs on a schedule (see config/celery.py beat schedule). Finds every order that has sat
    in DELIVERED for longer than ESCROW_AUTO_RELEASE_DAYS with no buyer action, and auto-confirms
    + releases escrow to the seller.

    Filtering on status=DELIVERED is what makes this safe: an order the buyer disputed has
    already moved to DISPUTED and simply will not match this query, so a dispute always wins a
    race against the auto-release window without needing any extra flag.
    """
    cutoff = timezone.now() - timezone.timedelta(days=settings.ESCROW_AUTO_RELEASE_DAYS)
    candidate_ids = list(
        Order.objects.filter(status=OrderStatus.DELIVERED, delivered_at__lte=cutoff).values_list(
            "id", flat=True
        )
    )

    released, skipped = [], []

    for order_id in candidate_ids:
        try:
            with transaction.atomic():
                # Re-fetch and lock inside the transaction: another request (buyer confirming,
                # or a dispute) may have moved this order on since the query above ran.
                order = Order.objects.select_for_update().get(id=order_id)
                if order.status != OrderStatus.DELIVERED:
                    skipped.append(order_id)
                    continue

                order.transition_to(
                    OrderStatus.CONFIRMED,
                    note=f"Auto-confirmed: no buyer action within {settings.ESCROW_AUTO_RELEASE_DAYS} days",
                )
                order.transition_to(
                    OrderStatus.COMPLETED, note="Auto-completed by escrow auto-release task"
                )
                release_escrow(order, auto=True)
                released.append(order_id)
        except InvalidOrderTransition as exc:
            logger.warning("Auto-release skipped order %s: %s", order_id, exc)
            skipped.append(order_id)
        except Exception:
            logger.exception("Auto-release failed for order %s", order_id)
            skipped.append(order_id)

    return {"released": released, "skipped": skipped}
