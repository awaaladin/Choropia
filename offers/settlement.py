"""
After the buyer taps Pay: unfinished checkouts, failed payments, and the handover code for orders without a rider.

* release_checkout(): an offer stuck in PAYMENT_PROCESSING (abandoned checkout, or Paystack says the charge failed) is
  opened again. Paystack is asked first, so a payment that did go through is applied, never thrown away. The unpaid
  order is cancelled, so if the buyer pays the old checkout link later the money is refunded automatically.
* Handover code (meet-up / seller delivers): 6 digits, hashed for checking plus an encrypted copy so the buyer can see
  it again. The buyer tells the seller once they hold the item; the seller enters it; escrow is released. Rider orders
  keep the dispatch app's code, which the rider enters.
"""
import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.db import transaction
from django.utils import timezone

from .models import HandoverCode, Offer
from .services import OfferError, get_for_participant, transition

logger = logging.getLogger(__name__)

PAYMENT_FAILED_NOTE = "Payment failed"


def _paystack_status(reference):
    from payments.paystack import PaystackClient

    return PaystackClient().verify_transaction(reference)


# --- unfinished checkouts -------------------------------------------------------------------------------------------


def release_checkout(offer_id, *, failed=False, now=None):
    from orders.models import Order
    from orders.state_machine import OrderStatus
    from payments.models import Payment
    from payments.paystack import PaystackError
    from payments.services import confirm_paystack_payment

    now = now or timezone.now()
    offer = Offer.objects.filter(pk=offer_id).first()
    if offer is None or offer.status != Offer.Status.PAYMENT_PROCESSING:
        return offer
    payment = Payment.objects.filter(order_id=offer.order_id).first() if offer.order_id else None
    if payment is not None and payment.status == Payment.Status.INITIALIZED:
        if payment.provider != Payment.Provider.PAYSTACK:
            return offer  # a crypto checkout can't be called off safely; staff handle these
        if payment.authorization_url:
            try:
                data = _paystack_status(payment.reference)
            except PaystackError:
                logger.warning("Could not check offer %s checkout with Paystack; will retry", offer.reference)
                return offer
            if data.get("status") == "success":
                with transaction.atomic():
                    confirm_paystack_payment(payment.reference, data)  # escrow, or a refund if anything is off
                return Offer.objects.get(pk=offer_id)
            failed = failed or data.get("status") == "failed"

    with transaction.atomic():
        offer = Offer.objects.select_for_update().get(pk=offer_id)
        if offer.status != Offer.Status.PAYMENT_PROCESSING:
            return offer
        order = Order.objects.select_for_update().filter(pk=offer.order_id).first() if offer.order_id else None
        if order is not None:
            if order.status != OrderStatus.PENDING_PAYMENT:
                return offer  # money arrived in the meantime; the payment path owns it now
            order.transition_to(OrderStatus.CANCELLED, note="Checkout from a chat offer was not completed")
        target = Offer.Status.EXPIRED if offer.expires_at <= now else Offer.Status.PENDING
        offer.order = None
        offer.delivery_method = ""
        offer.delivery_fee_kobo = 0
        offer.save(update_fields=["order", "delivery_method", "delivery_fee_kobo", "updated_at"])
        transition(offer, target, note=PAYMENT_FAILED_NOTE if failed else "Checkout not completed in time")
    return offer


def release_stale_checkouts(now=None, limit=50):
    """Scheduled job: checkouts left open longer than OFFER_CHECKOUT_TIMEOUT_MINUTES."""
    now = now or timezone.now()
    cutoff = now - timedelta(minutes=settings.OFFER_CHECKOUT_TIMEOUT_MINUTES)
    ids = list(
        Offer.objects.filter(status=Offer.Status.PAYMENT_PROCESSING, updated_at__lte=cutoff).values_list("pk", flat=True)[:limit]
    )
    released = []
    for pk in ids:
        try:
            offer = release_checkout(pk, now=now)
            if offer is not None and offer.status != Offer.Status.PAYMENT_PROCESSING:
                released.append(str(pk))
        except Exception:  # noqa: BLE001 - one bad offer must not stop the rest
            logger.exception("Could not release checkout for offer %s", pk)
    return {"released_checkouts": released}


def verify_offer_payment(*, user, offer_id):
    """Buyer, back from Paystack: settle the outcome now instead of waiting for the webhook."""
    from payments.models import Payment
    from payments.paystack import PaystackError
    from payments.services import confirm_paystack_payment

    offer = get_for_participant(offer_id, user)
    if user.pk != offer.buyer_id:
        raise OfferError("Only the buyer can check this payment.", status=403, code="forbidden")
    if offer.status != Offer.Status.PAYMENT_PROCESSING:
        return offer
    payment = Payment.objects.filter(order_id=offer.order_id).first()
    if payment is None or payment.provider != Payment.Provider.PAYSTACK or not payment.authorization_url:
        return offer
    try:
        data = _paystack_status(payment.reference)
    except PaystackError:
        raise OfferError("We couldn't reach the payment provider. Try again in a moment.", status=502, code="provider_unreachable")
    if data.get("status") == "success":
        with transaction.atomic():
            confirm_paystack_payment(payment.reference, data)
    elif data.get("status") == "failed":
        release_checkout(offer.pk, failed=True)
    return Offer.objects.get(pk=offer.pk)


def last_payment_failed(offer):
    if offer.status != Offer.Status.PENDING:
        return False
    last = offer.events.order_by("-created_at", "-id").first()
    return bool(last and last.note == PAYMENT_FAILED_NOTE)


# --- handover code (no rider) ---------------------------------------------------------------------------------------


class HandoverError(OfferError):
    pass


def issue_handover_code(order):
    """Called when an offer order without a rider lands in escrow. Idempotent."""
    existing = HandoverCode.objects.filter(order=order).first()
    if existing is not None:
        return existing
    code = f"{secrets.randbelow(10 ** 6):06d}"
    encrypted = None
    try:
        from dispatch import crypto

        if crypto.keys_configured():
            encrypted = crypto.encrypt(code.encode())
    except Exception:  # noqa: BLE001 - never block escrow on this; the buyer can still confirm receipt
        logger.exception("Could not encrypt the handover code for order %s", order.pk)
    return HandoverCode.objects.create(order=order, code_hash=make_password(code), code_encrypted=encrypted)


def handover_code_for_buyer(*, user, order_id):
    """The code to show the buyer (never the seller). Rider orders: the dispatch code the rider will ask for."""
    from orders.models import Order

    order = Order.objects.filter(pk=order_id, buyer=user).first()
    if order is None:
        raise HandoverError("Order not found.", status=404, code="not_found")
    delivery = getattr(order, "dispatch_delivery", None)
    if delivery is not None and delivery.handover_code:
        return {"code": delivery.handover_code, "entered_by": "rider", "used": False}
    row = HandoverCode.objects.filter(order=order).first()
    if row is None:
        raise HandoverError("There's no handover code for this order.", status=404, code="no_code")
    if row.used_at:
        return {"code": None, "entered_by": "seller", "used": True}
    if not row.code_encrypted:
        raise HandoverError("Your code can't be shown right now. When you have the item, tap Confirm receipt instead.",
                            status=503, code="code_unavailable")
    from dispatch import crypto

    return {"code": crypto.decrypt(row.code_encrypted).decode(), "entered_by": "seller", "used": False}


def confirm_handover(*, user, order_id, code):
    """Seller enters the buyer's code. Right code -> order completes, escrow released. Wrong codes are counted and the
    count is committed even though we raise."""
    from orders.models import Order

    order = Order.objects.filter(pk=order_id).first()
    if order is None or user.pk not in (order.buyer_id, order.seller_id):
        raise HandoverError("Order not found.", status=404, code="not_found")
    if user.pk != order.seller_id:
        raise HandoverError("Only the seller enters the buyer's code.", status=403, code="forbidden")
    if getattr(order, "dispatch_delivery", None) is not None:
        raise HandoverError("A rider is delivering this order; the rider enters the code.", status=409, code="rider_order")

    left = 0
    with transaction.atomic():
        row = HandoverCode.objects.select_for_update().filter(order=order).first()
        if row is None:
            raise HandoverError("There's no handover code for this order.", status=404, code="no_code")
        if row.used_at:
            raise HandoverError("This order was already handed over.", status=409, code="already_used")
        if row.attempts >= settings.HANDOVER_MAX_ATTEMPTS:
            raise HandoverError("Too many wrong codes. Ask the buyer to tap Confirm receipt, or contact support.",
                                status=423, code="code_locked")
        code = str(code or "").strip()
        right = len(code) == 6 and code.isdigit() and check_password(code, row.code_hash)
        if not right:
            row.attempts += 1
            row.save(update_fields=["attempts"])
            left = max(settings.HANDOVER_MAX_ATTEMPTS - row.attempts, 0)
    if not right:
        raise HandoverError(f"That code is not right. {left} tries left.", code="wrong_code", extra={"attempts_left": left})
    return _complete_handover(order.pk, user)


@transaction.atomic
def _complete_handover(order_id, user):
    from orders.models import Order
    from orders.state_machine import OrderStatus
    from payments.services import release_escrow

    stages = {
        OrderStatus.PAID_ESCROW: OrderStatus.COURIER_ASSIGNED,
        OrderStatus.COURIER_ASSIGNED: OrderStatus.IN_TRANSIT,
        OrderStatus.IN_TRANSIT: OrderStatus.DELIVERED,
        OrderStatus.DELIVERED: OrderStatus.CONFIRMED,
        OrderStatus.CONFIRMED: OrderStatus.COMPLETED,
    }
    order = Order.objects.select_for_update().get(pk=order_id)
    row = HandoverCode.objects.select_for_update().get(order=order)
    if row.used_at:
        raise HandoverError("This order was already handed over.", status=409, code="already_used")
    if order.status not in stages:
        raise HandoverError("This order can't be completed now (it may be disputed, refunded or already done).",
                            status=409, code="invalid_state")
    while order.status in stages:
        order.transition_to(stages[order.status], actor=user, note="[auto] Seller entered the buyer's handover code")
    row.used_at = timezone.now()
    row.save(update_fields=["used_at"])
    release_escrow(order, auto=False)
    return order
