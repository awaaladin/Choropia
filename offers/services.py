"""
The rules for escrow offers. Views stay thin; everything that decides or changes an offer is here.

Every status change goes through transition(): it checks the allow-list in models.TRANSITIONS, stamps the time,
writes an OfferEvent (the audit trail) and, after the transaction commits, pushes the new state to both people in the
conversation so their cards update in place.
"""
import logging
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from accounts import pin as pin_service
from accounts.models import is_verified_seller
from payments import fees
from payments.paystack import to_kobo

from .models import TRANSITIONS, Offer, OfferEvent

logger = logging.getLogger(__name__)
audit_log = logging.getLogger("choropia.audit")


class OfferError(Exception):
    def __init__(self, message, status=400, code="invalid", extra=None):
        super().__init__(message)
        self.message = message
        self.status = status
        self.code = code
        self.extra = extra or {}

    def as_response_data(self):
        return {"code": self.code, "detail": self.message, **self.extra}


class InvalidOfferTransition(OfferError):
    def __init__(self, current, target):
        super().__init__(f"This offer is {current.replace('_', ' ')} and can't become {target.replace('_', ' ')}.",
                         status=409, code="invalid_state")


# --- status changes ---------------------------------------------------------------------------------------------------


def transition(offer, target, actor=None, note=""):
    """The only sanctioned way to change Offer.status. Call inside a transaction, with the offer row locked."""
    if target not in TRANSITIONS.get(offer.status, set()):
        raise InvalidOfferTransition(offer.status, target)
    previous = offer.status
    offer.status = target
    now = timezone.now()
    if target == Offer.Status.PAID:
        offer.paid_at = now
    if target in Offer.TERMINAL_STATUSES:
        offer.closed_at = now
    offer.save()
    OfferEvent.objects.create(offer=offer, from_status=previous, to_status=target, actor=actor, note=note[:300])
    audit_log.info("offer.%s offer=%s from=%s actor=%s", target, offer.reference, previous, getattr(actor, "pk", None))
    broadcast_after_commit(offer)
    return offer


def expire_if_due(offer, now=None):
    """Lazily expires a PENDING offer whose time is up (the scheduled job does the same in bulk). Locked row required.
    Returns True if it was expired now."""
    now = now or timezone.now()
    if offer.status == Offer.Status.PENDING and offer.expires_at <= now:
        transition(offer, Offer.Status.EXPIRED, note="Time ran out")
        return True
    return False


# --- reading ----------------------------------------------------------------------------------------------------------


def role_of(offer, user):
    if user is None or not getattr(user, "is_authenticated", False):
        return None
    if user.pk == offer.seller_id:
        return "seller"
    if user.pk == offer.buyer_id:
        return "buyer"
    return None


def get_for_participant(offer_id, user, *, lock=False):
    """The offer if `user` is its buyer or seller; otherwise OfferError 404 (never 403, so ids can't be probed)."""
    from django.core.exceptions import ValidationError
    from django.db.models import Q

    qs = Offer.objects.filter(Q(seller=user) | Q(buyer=user))
    if lock:
        qs = qs.select_for_update()
    try:
        offer = qs.filter(pk=offer_id).first()
    except (ValidationError, ValueError):
        offer = None
    if offer is None:
        raise OfferError("Offer not found.", status=404, code="not_found")
    return offer


# --- creating ---------------------------------------------------------------------------------------------------------


def ceiling_kobo(listing_price_kobo):
    return listing_price_kobo * settings.OFFER_MAX_PERCENT_OF_LISTING // 100


def _clean_methods(methods, listing):
    if not isinstance(methods, (list, tuple)) or not methods:
        raise OfferError("Choose at least one way to hand the item over.", code="delivery_methods")
    valid = set(Offer.Delivery.values)
    cleaned = []
    for method in methods:
        if method not in valid:
            raise OfferError(f"Unknown delivery method: {method!r}.", code="delivery_methods")
        if method not in cleaned:
            cleaned.append(method)
    if Offer.Delivery.RIDER in cleaned and not _rider_available(listing):
        raise OfferError("Set up rider delivery for this listing before offering it.", code="delivery_methods")
    return cleaned


def _rider_available(listing):
    from dispatch.models import ListingDelivery

    return ListingDelivery.objects.filter(listing=listing, enabled=True).exists()


def _validate_amount(amount_kobo, listing_price_kobo):
    if isinstance(amount_kobo, bool) or not isinstance(amount_kobo, int):
        raise OfferError("Enter the amount as a whole number of kobo.", code="amount")
    if amount_kobo <= 0:
        raise OfferError("The amount must be more than ₦0.", code="amount")
    ceiling = ceiling_kobo(listing_price_kobo)
    if amount_kobo > ceiling:
        raise OfferError("An offer can't be higher than the listed price.", code="amount_above_listing",
                         extra={"max_amount_kobo": ceiling})


def create_offer(*, user, conversation, listing_id, amount_kobo, allowed_delivery_methods, note="", pin=""):
    """Seller-only. Validates everything cheap first, then the PIN (its attempt count is committed even on failure),
    then creates the offer, supersedes any live one for the same (conversation, listing) and posts the offer card into
    the chat, all in one transaction."""
    from chat.models import Message
    from listings.models import Listing

    if user.pk not in (conversation.user_low_id, conversation.user_high_id):
        raise OfferError("Only a participant in this conversation can make an offer.", status=403, code="forbidden")

    listing = Listing.objects.filter(pk=listing_id).first()
    if listing is None:
        raise OfferError("That listing isn't one of yours.", code="listing")
    if listing.owner_id != user.pk:
        if listing.owner_id in (conversation.user_low_id, conversation.user_high_id):
            raise OfferError("Only the seller in this conversation can make an offer.", status=403, code="forbidden")
        raise OfferError("That listing isn't one of yours.", code="listing")
    buyer = conversation.other_participant(user)
    if listing.status != Listing.Status.ACTIVE or listing.quantity < 1:
        raise OfferError("That listing is no longer for sale.", code="listing_unavailable")

    listing_price_kobo = to_kobo(listing.price)
    _validate_amount(amount_kobo, listing_price_kobo)
    methods = _clean_methods(allowed_delivery_methods, listing)
    note = (note or "").strip()[:300]

    # Outside the transaction below on purpose: a wrong PIN must stay counted.
    try:
        pin_service.verify_pin(user, pin)
    except pin_service.PinError as exc:
        raise OfferError(exc.message, status=423 if exc.code == "pin_locked" else 403, code=exc.code,
                         extra={k: v for k, v in (("retry_after", exc.retry_after), ("attempts_left", exc.attempts_left)) if v is not None})

    with transaction.atomic():
        live = list(
            Offer.objects.select_for_update()
            .filter(conversation=conversation, listing=listing, status__in=Offer.ACTIVE_STATUSES)
        )
        for old in live:
            if old.status == Offer.Status.PAYMENT_PROCESSING:
                raise OfferError("The buyer is paying for your current offer right now. Try again in a few minutes.",
                                 status=409, code="payment_in_progress")
        verified = is_verified_seller(user)
        fee, net = fees.split_kobo(amount_kobo, verified)
        for old in live:
            transition(old, Offer.Status.SUPERSEDED, actor=user, note="Replaced by a newer offer")

        offer = Offer.objects.create(
            conversation=conversation,
            listing=listing,
            seller_id=user.pk,
            buyer_id=buyer.pk,
            amount_kobo=amount_kobo,
            listing_price_kobo=listing_price_kobo,
            fee_kobo=fee,
            seller_net_kobo=net,
            seller_verified_snapshot=verified,
            allowed_delivery_methods=methods,
            note=note,
            expires_at=timezone.now() + timedelta(hours=settings.OFFER_TTL_HOURS),
        )
        OfferEvent.objects.create(offer=offer, from_status="", to_status=offer.status, actor=user, note="Offer made")
        audit_log.info("offer.created offer=%s seller=%s amount_kobo=%s", offer.reference, user.pk, amount_kobo)

        # The body is a plain-text fallback for app versions that don't know offer cards yet.
        Message.objects.create(
            conversation=conversation,
            sender=user,
            message_type=Message.MessageType.OFFER,
            offer=offer,
            body=f"Offer: {format_naira(amount_kobo)} for {listing.title}",
        )
        conversation.save(update_fields=["updated_at"])
        broadcast_after_commit(offer)
    return offer


def create_offer_checkout(*, user, offer_id, delivery_method):
    """Create the escrow order at the offer's locked price, never the listing's public price."""
    from chat.models import Conversation
    from listings.models import Listing
    from orders.models import Order

    order = None
    expired = False
    with transaction.atomic():
        offer = get_for_participant(offer_id, user, lock=True)
        if user.pk != offer.buyer_id:
            raise OfferError("Only the buyer can pay this offer.", status=403, code="forbidden")
        if delivery_method not in offer.allowed_delivery_methods:
            raise OfferError("Choose one of the handover methods in this offer.", code="delivery_method")
        if delivery_method == Offer.Delivery.RIDER and not _rider_available(offer.listing):
            raise OfferError("Rider delivery is no longer available for this listing.", code="delivery_method")
        if expire_if_due(offer):
            expired = True
        elif offer.status == Offer.Status.PAYMENT_PROCESSING and offer.order_id:
            order = Order.objects.select_for_update().get(pk=offer.order_id)
            if order.status != Order.Status.PENDING_PAYMENT:
                raise OfferError("The order for this offer is no longer payable.", status=409, code="invalid_state")
            if offer.delivery_method != delivery_method:
                raise OfferError("A checkout is already open for this offer.", status=409, code="payment_in_progress")
        else:
            if offer.status != Offer.Status.PENDING:
                raise OfferError("This offer is no longer available for payment.", status=409, code="invalid_state")

            listing = Listing.objects.select_for_update().get(pk=offer.listing_id)
            if listing.status != Listing.Status.ACTIVE or listing.quantity < 1:
                raise OfferError("That listing is no longer for sale.", status=409, code="listing_unavailable")

            order = Order.objects.create(
                listing=listing,
                buyer=offer.buyer,
                seller=offer.seller,
                price=Decimal(offer.amount_kobo) / 100,
            )
            conversation = Conversation.objects.select_for_update().get(pk=offer.conversation_id)
            conversation.orders.add(order)
            if conversation.order_id is None or conversation.order.status == Order.Status.CANCELLED:
                conversation.order = order
                conversation.save(update_fields=["order", "updated_at"])
            offer.order = order
            offer.delivery_method = delivery_method
            offer.delivery_fee_kobo = 0
            offer.save(update_fields=["order", "delivery_method", "delivery_fee_kobo", "updated_at"])
            transition(offer, Offer.Status.PAYMENT_PROCESSING, actor=user, note="Buyer started escrow checkout")
    if expired:
        raise OfferError("This offer has expired.", status=409, code="expired")
    if order is None:
        raise OfferError("The offer checkout could not be created.", status=500, code="checkout_error")
    return order


def format_naira(kobo):
    naira, k = divmod(int(kobo), 100)
    return f"₦{naira:,}" + (f".{k:02d}" if k else "")


# --- closing ----------------------------------------------------------------------------------------------------------


def cancel_offer(*, user, offer_id):
    with transaction.atomic():
        offer = get_for_participant(offer_id, user, lock=True)
        if user.pk != offer.seller_id:
            raise OfferError("Only the seller can cancel this offer.", status=403, code="forbidden")
        if expire_if_due(offer):
            return offer
        if offer.status == Offer.Status.PAYMENT_PROCESSING:
            raise OfferError("The buyer is paying for this offer right now.", status=409, code="payment_in_progress")
        transition(offer, Offer.Status.CANCELLED, actor=user, note="Cancelled by the seller")
    return offer


def decline_offer(*, user, offer_id):
    with transaction.atomic():
        offer = get_for_participant(offer_id, user, lock=True)
        if user.pk != offer.buyer_id:
            raise OfferError("Only the buyer can decline this offer.", status=403, code="forbidden")
        if expire_if_due(offer):
            return offer
        transition(offer, Offer.Status.DECLINED, actor=user, note="Declined by the buyer")
    return offer


def expire_due_offers(now=None, limit=500):
    """Scheduled job: PENDING offers past their time become EXPIRED. Safe to run often and in parallel."""
    now = now or timezone.now()
    expired = 0
    ids = list(Offer.objects.filter(status=Offer.Status.PENDING, expires_at__lte=now).values_list("pk", flat=True)[:limit])
    for pk in ids:
        with transaction.atomic():
            offer = Offer.objects.select_for_update().filter(pk=pk).first()
            if offer is not None and expire_if_due(offer, now):
                expired += 1
    from .settlement import release_stale_checkouts

    return {"expired": expired, **release_stale_checkouts(now)}


# --- realtime ---------------------------------------------------------------------------------------------------------


def broadcast_after_commit(offer):
    offer_id = offer.pk
    transaction.on_commit(lambda: broadcast(offer_id))


def broadcast(offer_id):
    """Tells both people's open chats that this offer changed. Each connection re-reads the offer and serializes it for
    its own user (so the buyer's copy never carries the fee). A realtime outage never fails the change itself; clients
    that are polling, or that reconnect, pick the new state up from the API."""
    from chat.realtime import group_name_for

    try:
        offer = Offer.objects.only("conversation_id").get(pk=offer_id)
        message_id = offer.messages.order_by("created_at").values_list("pk", flat=True).first()
        if message_id is None:
            return
        _group_send(
            group_name_for(offer.conversation_id),
            {"type": "offer.updated", "message_id": message_id, "offer_id": str(offer_id)},
        )
    except Exception:  # noqa: BLE001
        logger.warning("Realtime broadcast failed for offer %s", offer_id, exc_info=True)


def _group_send(group, event):
    from asgiref.sync import async_to_sync
    from channels.layers import get_channel_layer

    layer = get_channel_layer()
    if layer is not None:
        async_to_sync(layer.group_send)(group, event)
