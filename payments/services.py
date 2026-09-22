import uuid

from django.conf import settings
from django.utils import timezone

from orders.state_machine import OrderStatus

from .models import Payment
from .paystack import PaystackClient


def _client():
    return PaystackClient()


def generate_reference(order):
    return f"order-{order.id}-{uuid.uuid4().hex[:10]}"


def initialize_payment(order, callback_url=None):
    payment, _ = Payment.objects.get_or_create(
        order=order,
        defaults={"reference": generate_reference(order), "amount": order.price},
    )
    if payment.status != Payment.Status.INITIALIZED:
        return payment

    amount_kobo = int(payment.amount * 100)
    data = _client().initialize_transaction(
        email=order.buyer.email,
        amount_kobo=amount_kobo,
        reference=payment.reference,
        callback_url=callback_url,
    )
    payment.authorization_url = data.get("authorization_url", "")
    payment.save(update_fields=["authorization_url"])
    return payment


def confirm_payment(reference, raw_payload=None):
    """Called from the Paystack webhook once a charge succeeds. Marks the payment as held in
    escrow and advances the order from PENDING_PAYMENT -> PAID_ESCROW."""
    try:
        payment = Payment.objects.select_related("order").get(reference=reference)
    except Payment.DoesNotExist:
        return None

    if payment.status != Payment.Status.INITIALIZED:
        return payment  # already processed - webhooks can be delivered more than once

    payment.status = Payment.Status.PAID_HELD
    payment.paid_at = timezone.now()
    payment.raw_webhook_payload = raw_payload
    payment.save(update_fields=["status", "paid_at", "raw_webhook_payload"])

    payment.order.transition_to(OrderStatus.PAID_ESCROW, note="Payment confirmed via Paystack webhook")
    return payment


def release_escrow(order, auto=False):
    """Releases held funds to the seller. Only valid once the order itself has reached a
    completed state — this function does not change order status, it only settles the money."""
    try:
        payment = order.payment
    except Payment.DoesNotExist:
        return None

    if payment.status == Payment.Status.RELEASED:
        return payment
    if payment.status != Payment.Status.PAID_HELD:
        raise ValueError(f"Cannot release a payment in status '{payment.status}'.")

    if settings.PAYSTACK_SECRET_KEY:
        # Real payout requires the seller to have a linked transfer recipient; until that
        # onboarding flow exists we record the release without a live transfer rather than
        # failing the whole order-completion flow.
        pass

    payment.status = Payment.Status.RELEASED
    payment.released_at = timezone.now()
    payment.auto_released = auto
    payment.save(update_fields=["status", "released_at", "auto_released"])
    return payment


def refund_escrow(order):
    try:
        payment = order.payment
    except Payment.DoesNotExist:
        return None

    if payment.status == Payment.Status.REFUNDED:
        return payment
    if payment.status != Payment.Status.PAID_HELD:
        raise ValueError(f"Cannot refund a payment in status '{payment.status}'.")

    if settings.PAYSTACK_SECRET_KEY:
        _client().refund(payment.reference)

    payment.status = Payment.Status.REFUNDED
    payment.refunded_at = timezone.now()
    payment.save(update_fields=["status", "refunded_at"])
    return payment
