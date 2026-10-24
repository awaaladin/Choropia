import logging

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from orders.state_machine import OrderStatus

from .gaxtron import GaxtronClient
from .models import Payment
from .naming import make_reference, paystack_metadata
from .paystack import PaystackClient, from_kobo

logger = logging.getLogger(__name__)


def _client():
    return GaxtronClient()


def _paystack():
    return PaystackClient()


def generate_reference(order):
    return make_reference("ORDER")


def initialize_payment(order, callback_url=None):
    provider = settings.PAYMENT_PROVIDER
    payment, created = Payment.objects.get_or_create(
        order=order,
        defaults={"reference": generate_reference(order), "amount": order.price, "provider": provider},
    )
    if payment.status != Payment.Status.INITIALIZED:
        return payment

    if not created and payment.provider != provider:
        # The platform switched provider since this checkout was started; start a fresh one
        # rather than sending the buyer to the old provider's page.
        payment.provider = provider
        payment.reference = generate_reference(order)
        payment.authorization_url = ""
        payment.save(update_fields=["provider", "reference", "authorization_url"])

    if provider == Payment.Provider.PAYSTACK:
        return _initialize_paystack(payment)
    return _initialize_gaxtron(payment)


def _initialize_paystack(payment):
    if payment.authorization_url:
        return payment  # Paystack rejects a second initialize with the same reference
    order = payment.order
    data = _paystack().initialize_transaction(
        email=order.buyer.email,
        amount=payment.amount,
        reference=payment.reference,
        # Server-chosen, never the client's: Paystack sends the buyer back to the order page.
        callback_url=f"{settings.CHOROPIA_SITE_URL.rstrip('/')}/orders/{order.id}",
        metadata=paystack_metadata(
            "ORDER",
            f"Order #{order.id}: {order.listing.title}",
            order_id=order.id,
            listing_id=order.listing_id,
            buyer_id=order.buyer_id,
            seller_id=order.seller_id,
        ),
    )
    payment.authorization_url = data.get("authorization_url", "")
    payment.save(update_fields=["authorization_url"])
    return payment


def _initialize_gaxtron(payment):
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


def _mark_held(payment, note):
    payment.status = Payment.Status.PAID_HELD
    payment.paid_at = timezone.now()
    payment.order.transition_to(OrderStatus.PAID_ESCROW, note=note)


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

    _mark_held(payment, "Payment confirmed via Gaxtron")
    if tx_hash:
        payment.tx_hash = tx_hash
    payment.raw_webhook_payload = raw_payload
    payment.save(update_fields=["status", "paid_at", "tx_hash", "raw_webhook_payload"])
    return payment


@transaction.atomic
def confirm_paystack_payment(reference, data, raw_payload=None):
    """Applies a Paystack transaction (from the webhook or a verify call) to its payment.

    The row lock plus the INITIALIZED check means the webhook, the buyer's verify call and the
    poller can all report the same charge and the order still moves to escrow exactly once.
    Only a successful NGN charge of at least the order amount counts."""
    payment = Payment.objects.select_for_update().select_related("order").filter(reference=reference).first()
    if payment is None or payment.status != Payment.Status.INITIALIZED:
        return payment
    if data.get("status") != "success":
        return payment  # abandoned/failed attempts can still be retried on the same checkout

    paid = from_kobo(data.get("amount") or 0)
    if data.get("currency", "NGN") != "NGN" or paid < payment.amount:
        logger.error("Paystack %s: expected NGN %s, got %s %s", reference, payment.amount, data.get("currency"), paid)
        payment.status = Payment.Status.FAILED
        payment.raw_webhook_payload = raw_payload or data
        payment.save(update_fields=["status", "raw_webhook_payload"])
        return payment

    _mark_held(payment, "Payment confirmed via Paystack")
    payment.paystack_transaction_id = str(data.get("id") or "")
    payment.raw_webhook_payload = raw_payload or data
    payment.save(update_fields=["status", "paid_at", "paystack_transaction_id", "raw_webhook_payload"])
    return payment


def verify_paystack_payment(payment):
    """Asks Paystack directly, so the buyer doesn't wait on the webhook after checkout."""
    if payment.provider != Payment.Provider.PAYSTACK or payment.status != Payment.Status.INITIALIZED:
        return payment
    data = _paystack().verify_transaction(payment.reference)
    return confirm_paystack_payment(payment.reference, data) or payment


def release_escrow(order, auto=False):
    """Releases held funds to the seller. Only valid once the order itself has reached a
    completed state — this function does not change order status, it only settles the money.

    Neither provider pays the seller automatically yet: Gaxtron has no payout endpoint at all,
    and a Paystack transfer needs the seller's bank account as a transfer recipient, which
    Choropia doesn't collect yet. So this records the release; the seller is paid out of the
    Paystack balance by hand (the payment's reference is in the admin)."""
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
    """Paystack payments are refunded to the buyer for real through Paystack's refund API.
    Gaxtron has no refund endpoint, so for those this only records the refund without moving
    crypto back to the buyer."""
    try:
        payment = order.payment
    except Payment.DoesNotExist:
        return None

    if payment.status == Payment.Status.REFUNDED:
        return payment
    if payment.status != Payment.Status.PAID_HELD:
        raise ValueError(f"Cannot refund a payment in status '{payment.status}'.")

    if payment.provider == Payment.Provider.PAYSTACK:
        _paystack().refund(payment.reference)  # raises PaystackError, rolling back the caller

    payment.status = Payment.Status.REFUNDED
    payment.refunded_at = timezone.now()
    payment.save(update_fields=["status", "refunded_at"])
    return payment
