import uuid

from django.conf import settings
from django.utils import timezone

from orders.state_machine import OrderStatus

from .gaxtron import GaxtronClient
from .models import Payment


def _client():
    return GaxtronClient()


def generate_reference(order):
    return f"order-{order.id}-{uuid.uuid4().hex[:10]}"


def initialize_payment(order, callback_url=None):
    payment, _ = Payment.objects.get_or_create(
        order=order,
        defaults={"reference": generate_reference(order), "amount": order.price},
    )
    if payment.status != Payment.Status.INITIALIZED:
        return payment

    client = _client()
    eth_amount = client.ngn_to_eth(payment.amount)
    data = client.create_payment(
        eth_amount=eth_amount,
        callback_url=settings.GAXTRON_CALLBACK_URL,
        idempotency_key=payment.reference,
    )
    payment.authorization_url = data.get("checkout_url", "")
    payment.gaxtron_payment_id = data.get("payment_id")
    payment.crypto_amount = eth_amount
    payment.crypto_currency = data.get("currency", "ETH")
    payment.wallet_address = data.get("wallet_address", "")
    payment.save(
        update_fields=[
            "authorization_url",
            "gaxtron_payment_id",
            "crypto_amount",
            "crypto_currency",
            "wallet_address",
        ]
    )
    return payment


def confirm_payment(gaxtron_payment_id, tx_hash=None, raw_payload=None):
    """Called once gaxtron reports a payment as confirmed — either via its webhook, or via
    payments.tasks.poll_gaxtron_payments_task (see gaxtron.py for why the latter is what dev
    actually relies on). Marks the payment as held in escrow and advances the order from
    PENDING_PAYMENT -> PAID_ESCROW."""
    try:
        payment = Payment.objects.select_related("order").get(gaxtron_payment_id=gaxtron_payment_id)
    except Payment.DoesNotExist:
        return None

    if payment.status != Payment.Status.INITIALIZED:
        return payment  # already processed - webhook + poller can both fire for the same payment

    payment.status = Payment.Status.PAID_HELD
    payment.paid_at = timezone.now()
    if tx_hash:
        payment.tx_hash = tx_hash
    payment.raw_webhook_payload = raw_payload
    payment.save(update_fields=["status", "paid_at", "tx_hash", "raw_webhook_payload"])

    payment.order.transition_to(OrderStatus.PAID_ESCROW, note="Payment confirmed via Gaxtron")
    return payment


def release_escrow(order, auto=False):
    """Releases held funds to the seller. Only valid once the order itself has reached a
    completed state — this function does not change order status, it only settles the money.

    Gaxtron has no payout/transfer endpoint (it only collects into per-payment wallets it
    custodies) — same gap that existed under Paystack, which needed a transfer-recipient
    onboarding flow that was never built — so this records the release without a live payout."""
    try:
        payment = order.payment
    except Payment.DoesNotExist:
        return None

    if payment.status == Payment.Status.RELEASED:
        return payment
    if payment.status != Payment.Status.PAID_HELD:
        raise ValueError(f"Cannot release a payment in status '{payment.status}'.")

    payment.status = Payment.Status.RELEASED
    payment.released_at = timezone.now()
    payment.auto_released = auto
    payment.save(update_fields=["status", "released_at", "auto_released"])
    return payment


def refund_escrow(order):
    """Gaxtron has no refund endpoint either — same as release_escrow, this records the refund
    without moving crypto back to the buyer."""
    try:
        payment = order.payment
    except Payment.DoesNotExist:
        return None

    if payment.status == Payment.Status.REFUNDED:
        return payment
    if payment.status != Payment.Status.PAID_HELD:
        raise ValueError(f"Cannot refund a payment in status '{payment.status}'.")

    payment.status = Payment.Status.REFUNDED
    payment.refunded_at = timezone.now()
    payment.save(update_fields=["status", "refunded_at"])
    return payment
