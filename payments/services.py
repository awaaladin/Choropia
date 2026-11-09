import logging
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from orders.state_machine import OrderStatus

from .gaxtron import GaxtronClient
from .models import Payment
from .naming import make_reference, paystack_metadata
from .paystack import PaystackClient, PaystackError, from_kobo

logger = logging.getLogger(__name__)


def _client():
    return GaxtronClient()


def _paystack():
    return PaystackClient()


def generate_reference(order):
    return make_reference("ORDER")


def payable_amount(order):
    """What the buyer is charged: the item price plus their share of the delivery fee (if they chose delivery)."""
    delivery = getattr(order, "dispatch_delivery", None)
    if delivery is not None and delivery.status != "cancelled":
        return Decimal(order.price) + delivery.buyer_share
    return Decimal(order.price)


def initialize_payment(order, callback_url=None, return_to_app=False):
    provider = settings.PAYMENT_PROVIDER
    payment, created = Payment.objects.get_or_create(
        order=order,
        defaults={"reference": generate_reference(order), "amount": payable_amount(order), "provider": provider, "return_to_app": return_to_app},
    )
    if payment.status != Payment.Status.INITIALIZED:
        return payment

    if not created and payment.return_to_app != return_to_app:
        # A checkout opened from the website, now paid from the app (or the other way round): Paystack remembers where to send
        # the buyer afterwards, so start a fresh one that goes back to the right place.
        payment.return_to_app = return_to_app
        payment.reference = generate_reference(order)
        payment.authorization_url = ""
        payment.save(update_fields=["return_to_app", "reference", "authorization_url"])

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
        callback_url=(
            f"{settings.CHOROPIA_SITE_URL.rstrip('/')}/pay/return/{order.id}/"
            if payment.return_to_app
            else f"{settings.CHOROPIA_SITE_URL.rstrip('/')}/orders/{order.id}"
        ),
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


def reserve_listing(order):
    """Takes one unit out of stock the moment money for it arrives. Returns False if there is none left (the last one went to
    another buyer a moment earlier, or the listing was removed), in which case the caller must hand this buyer's money back
    instead of holding it. The listing is marked sold when the last unit goes."""
    from listings.models import Listing

    listing = Listing.objects.select_for_update().get(pk=order.listing_id)
    if listing.status != Listing.Status.ACTIVE or listing.quantity < 1:
        return False
    listing.quantity -= 1
    if listing.quantity == 0:
        listing.status = Listing.Status.SOLD
        listing.sold_at = timezone.now()
        days = settings.SOLD_LISTING_DEFAULT_DAYS
        if days not in settings.SOLD_LISTING_DURATIONS:
            raise ValueError("SOLD_LISTING_DEFAULT_DAYS must be one of the configured sold durations.")
        listing.market_visible_until = listing.sold_at + timedelta(days=days)
    update_fields = ["quantity", "status", "updated_at"]
    if listing.quantity == 0:
        update_fields.extend(["sold_at", "market_visible_until"])
        from django.contrib.contenttypes.models import ContentType
        from notifications.models import Notification

        Notification.objects.create(
            recipient=order.seller,
            actor=order.buyer,
            notification_type=Notification.Type.ORDER_STATUS,
            verb=f'Your listing "{listing.title}" sold. Choose how long it stays visible in the market.',
            target_content_type=ContentType.objects.get_for_model(order),
            target_object_id=order.pk,
        )
    listing.save(update_fields=update_fields)
    return True


def reopen_listing(order):
    """Puts one unit back on sale (a paid order was refunded or cancelled before the item changed hands)."""
    from listings.models import Listing

    listing = Listing.objects.select_for_update().get(pk=order.listing_id)
    if listing.status == Listing.Status.REMOVED:
        return
    listing.quantity += 1
    if listing.status == Listing.Status.SOLD:
        listing.status = Listing.Status.ACTIVE
        listing.sold_at = None
        listing.market_visible_until = None
    listing.save(update_fields=["quantity", "status", "sold_at", "market_visible_until", "updated_at"])


def _hold_for_refund(payment, data, raw_payload, note="Item no longer available"):
    """A buyer paid for an item that sold to someone else a moment earlier. Cancel their order and
    give the money straight back; a scheduler retries if Paystack is unavailable."""
    payment.status = Payment.Status.REFUND_PENDING
    payment.paid_at = timezone.now()
    payment.paystack_transaction_id = str(data.get("id") or "")
    payment.raw_webhook_payload = raw_payload or data
    payment.save(update_fields=["status", "paid_at", "paystack_transaction_id", "raw_webhook_payload"])
    from . import ledger

    ledger.received_for_refund(payment, note=note)
    if payment.order.status != OrderStatus.CANCELLED:  # already cancelled by the buyer or seller: nothing more to change
        payment.order.transition_to(OrderStatus.CANCELLED, note=f"{note}; payment is being refunded")
    transaction.on_commit(lambda pid=payment.pk: process_pending_refund(pid))
    logger.warning("Payment %s arrived for an unavailable item; refunding", payment.reference)
    return payment


def _already_refunded(exc):
    text = str(exc).lower()
    return "already" in text and "refund" in text


def process_pending_refund(payment_id):
    """Refunds a REFUND_PENDING payment. Idempotent and safe to retry."""
    try:
        with transaction.atomic():
            payment = Payment.objects.select_for_update().select_related("order").get(pk=payment_id)
            if payment.status != Payment.Status.REFUND_PENDING:
                return payment
        try:
            _paystack().refund(payment.reference)
        except PaystackError as exc:
            if not _already_refunded(exc):
                logger.error("Refund for payment %s failed (will retry): %s", payment.reference, exc)
                return payment
        with transaction.atomic():
            changed = Payment.objects.filter(pk=payment.pk, status=Payment.Status.REFUND_PENDING).update(
                status=Payment.Status.REFUNDED, refunded_at=timezone.now()
            )
            payment.refresh_from_db()
            if changed:
                from . import ledger

                ledger.refunded(payment)
        return payment
    except Exception:  # noqa: BLE001 - never raise into a webhook or a scheduler
        logger.exception("Unexpected error refunding payment %s", payment_id)
        return None


def retry_pending_refunds():
    ids = list(Payment.objects.filter(status=Payment.Status.REFUND_PENDING).values_list("pk", flat=True)[:25])
    done = [pid for pid in ids if (p := process_pending_refund(pid)) is not None and p.status == Payment.Status.REFUNDED]
    return {"pending": len(ids), "refunded": done}


def _mark_held(payment, note):
    from . import ledger

    payment.status = Payment.Status.PAID_HELD
    payment.paid_at = timezone.now()
    payment.order.transition_to(OrderStatus.PAID_ESCROW, note=note)
    ledger.held(payment)
    try:
        from dispatch import services as dispatch_services

        dispatch_services.on_order_paid(payment.order)  # handover code + job alerts to the seller's drivers
    except Exception:  # noqa: BLE001 - never block escrow on a dispatch problem; the nudge job catches it
        logger.exception("Dispatch could not start for payment %s", payment.pk)
    try:
        from notifications import emails

        emails.send_payment_received(payment)  # buyer receipt + seller "dispatch it"; sent after commit
    except Exception:  # noqa: BLE001 - never block escrow on an email problem
        logger.exception("Payment emails could not be prepared for payment %s", payment.pk)


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

    # Paid on a checkout that was left open after the order was cancelled: give the money straight back.
    if payment.order.status == OrderStatus.CANCELLED or not reserve_listing(payment.order):
        return _hold_for_refund(payment, data, raw_payload)

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

    Paystack payments are paid out to the seller automatically (minus the platform commission) by
    payments/payouts.py once this transaction commits. Gaxtron has no payout endpoint, so for
    those the release is only recorded."""
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

    # Pay the seller (minus Choropia's commission). The transfer itself is only sent after the
    # surrounding transaction commits; see payments/payouts.py.
    from . import payouts

    payouts.release_hook(payment)
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
        try:
            _paystack().refund(payment.reference)  # any other PaystackError rolls back the caller
        except PaystackError as exc:
            if not _already_refunded(exc):
                raise

    payment.status = Payment.Status.REFUNDED
    payment.refunded_at = timezone.now()
    payment.save(update_fields=["status", "refunded_at"])
    from . import ledger

    ledger.refunded(payment)
    return payment
