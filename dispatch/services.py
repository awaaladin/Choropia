"""Dispatch rules. Views stay thin; everything that matters (money, who may do what, the
first-driver-wins race) is decided here so it can be tested without HTTP."""
import logging
import secrets
from decimal import ROUND_DOWN, Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from notifications import emails
from notifications.models import Notification
from notifications.services import create_notification
from orders.models import Order
from orders.state_machine import OrderStatus

from .models import (
    Area,
    DeliveryOffer,
    DriverProfile,
    DriverRoute,
    ListingDelivery,
    OrderDelivery,
)

logger = logging.getLogger(__name__)
TWO_PLACES = Decimal("0.01")


class DispatchError(Exception):
    """A rule was broken; the message is safe to show the person."""

    def __init__(self, message, code="invalid", status=400):
        super().__init__(message)
        self.message, self.code, self.status = message, code, status


# --- who pays what -----------------------------------------------------------------------------


def split_fee(fee, payer):
    """(buyer_share, seller_share). 'split' is always an exact 50/50 (the odd kobo goes to the seller)."""
    fee = Decimal(fee).quantize(TWO_PLACES)
    if payer == ListingDelivery.Payer.BUYER:
        return fee, Decimal("0.00")
    if payer == ListingDelivery.Payer.SELLER:
        return Decimal("0.00"), fee
    buyer = (fee / 2).quantize(TWO_PLACES, rounding=ROUND_DOWN)
    return buyer, fee - buyer


def driver_net(fee):
    """What a driver actually receives for a fee, after Choropia's driver commission."""
    from payments.payouts import commission_split

    return commission_split(fee, settings.DRIVER_COMMISSION_PERCENT)[1]


def _notify(user, text, target=None, subject=None, body=None, link=""):
    """In-app notification plus an email; neither may ever break the caller."""
    try:
        create_notification(user, Notification.Type.DISPATCH, text, target=target)
        emails.send_dispatch_notice(user, subject or text, subject or text, body or text, link)
    except Exception:  # noqa: BLE001
        logger.exception("Could not notify user %s about dispatch", getattr(user, "id", None))


# --- areas ---------------------------------------------------------------------------------------


def add_area(name, user):
    name = " ".join((name or "").split())
    if len(name) < 3 or len(name) > 80:
        raise DispatchError("Enter an area name between 3 and 80 characters.")
    if any(ch.isdigit() for ch in name) and sum(ch.isdigit() for ch in name) > 4:
        raise DispatchError("That does not look like an area name.")
    from django.utils.text import slugify

    existing = Area.objects.filter(slug=slugify(name)).first()
    if existing:
        if not existing.is_active:
            raise DispatchError("That area is not available.")
        return existing, False
    return Area.objects.create(name=name, added_by=user), True


# --- the seller's setup for a listing -----------------------------------------------------------


def eligible_route(driver, from_area, to_area):
    return DriverRoute.objects.filter(
        driver=driver, from_area=from_area, to_area=to_area, is_active=True
    ).first()


@transaction.atomic
def set_listing_delivery(listing, user, enabled, payer, pickup_area, driver_ids):
    if listing.owner_id != user.id:
        raise DispatchError("Only the seller can change delivery for this listing.", status=403)
    if payer not in ListingDelivery.Payer.values:
        raise DispatchError("Choose who pays for delivery: buyer, seller or split.")
    drivers = list(DriverProfile.objects.filter(pk__in=driver_ids, status=DriverProfile.Status.APPROVED))
    if enabled and not drivers:
        raise DispatchError("Pick at least one approved driver (picking more than one means a faster pickup).")
    if enabled and len(drivers) != len(set(driver_ids)):
        raise DispatchError("One of the drivers you picked is not available.")
    for driver in drivers:
        if not DriverRoute.objects.filter(driver=driver, from_area=pickup_area, is_active=True).exists():
            raise DispatchError(f"{driver.public_name} does not deliver from {pickup_area.name}.")
    options, _ = ListingDelivery.objects.update_or_create(
        listing=listing, defaults={"enabled": enabled, "payer": payer, "pickup_area": pickup_area}
    )
    options.drivers.set(drivers)
    return options


def options_for_buyer(listing, dropoff_area=None):
    """The drivers a seller chose, with exact prices to the buyer's area. No contact details."""
    options = getattr(listing, "delivery_options", None)
    if options is None or not options.enabled:
        return None
    result = []
    for driver in options.drivers.filter(status=DriverProfile.Status.APPROVED):
        routes = DriverRoute.objects.filter(driver=driver, from_area=options.pickup_area, is_active=True).select_related("to_area")
        if dropoff_area is not None:
            routes = routes.filter(to_area=dropoff_area)
        result.append((driver, list(routes)))
    return options, result


# --- checkout ---------------------------------------------------------------------------------


@transaction.atomic
def choose_delivery(order, user, dropoff_area, driver, note=""):
    """The buyer picks where to and which driver's price. Must happen before they pay."""
    from payments.models import Payment

    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.buyer_id != user.id:
        raise DispatchError("Only the buyer can choose delivery.", status=403)
    if order.status != OrderStatus.PENDING_PAYMENT:
        raise DispatchError("Delivery can only be chosen before you pay.")
    options = ListingDelivery.objects.filter(listing_id=order.listing_id, enabled=True).first()
    if options is None:
        raise DispatchError("This item is not offered with delivery.")
    if not options.drivers.filter(pk=driver.pk, status=DriverProfile.Status.APPROVED).exists():
        raise DispatchError("That driver is not one of this seller's drivers.")
    route = eligible_route(driver, options.pickup_area, dropoff_area)
    if route is None:
        raise DispatchError(f"{driver.public_name} does not deliver to {dropoff_area.name}.")

    fee = route.price
    buyer_share, seller_share = split_fee(fee, options.payer)
    from payments.payouts import commission_split

    if commission_split(Decimal(order.price))[1] - seller_share < 0:
        raise DispatchError("This item costs too little for the seller to cover that delivery fee. Pick a different option.")

    delivery, _ = OrderDelivery.objects.update_or_create(
        order=order,
        defaults={
            "pickup_area": options.pickup_area,
            "dropoff_area": dropoff_area,
            "dropoff_note": (note or "")[:300],
            "payer": options.payer,
            "fee": fee,
            "buyer_share": buyer_share,
            "seller_share": seller_share,
            "status": OrderDelivery.Status.AWAITING_PAYMENT,
        },
    )
    # A checkout already opened for a different total must be reissued: Paystack will not accept a
    # second initialize on the same reference, and the buyer must be charged exactly the new total.
    payment = Payment.objects.select_for_update().filter(order=order).first()
    if payment is not None and payment.status == Payment.Status.INITIALIZED:
        from payments.services import generate_reference

        payment.amount = Decimal(order.price) + buyer_share
        payment.reference = generate_reference(order)
        payment.authorization_url = ""
        payment.save(update_fields=["amount", "reference", "authorization_url", "updated_at"])
    return delivery


def clear_delivery(order, user):
    """The buyer drops delivery before paying (they will collect it from the seller instead)."""
    from payments.models import Payment

    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order.pk)
        if order.buyer_id != user.id:
            raise DispatchError("Only the buyer can change delivery.", status=403)
        if order.status != OrderStatus.PENDING_PAYMENT:
            raise DispatchError("Delivery can only be changed before you pay.")
        OrderDelivery.objects.filter(order=order).delete()
        payment = Payment.objects.select_for_update().filter(order=order).first()
        if payment is not None and payment.status == Payment.Status.INITIALIZED and payment.amount != Decimal(order.price):
            from payments.services import generate_reference

            payment.amount = Decimal(order.price)
            payment.reference = generate_reference(order)
            payment.authorization_url = ""
            payment.save(update_fields=["amount", "reference", "authorization_url", "updated_at"])


# --- after payment: tell the drivers ---------------------------------------------------------------


def _eligible_drivers(delivery):
    """Selected drivers who are approved, switched on, and serve this trip at or below the fixed fee."""
    options = ListingDelivery.objects.filter(listing_id=delivery.order.listing_id).first()
    chosen = options.drivers.all() if options else DriverProfile.objects.none()
    result = []
    for driver in chosen.filter(status=DriverProfile.Status.APPROVED, available=True):
        route = eligible_route(driver, delivery.pickup_area, delivery.dropoff_area)
        if route is not None and route.price <= delivery.fee:
            result.append(driver)
    return result


def _make_code():
    return f"{secrets.randbelow(10**6):06d}"


def on_order_paid(order):
    """Called when the payment lands in escrow. Creates the handover code and alerts every selected driver."""
    delivery = OrderDelivery.objects.select_for_update().filter(order=order).first()
    if delivery is None or delivery.status != OrderDelivery.Status.AWAITING_PAYMENT:
        return None
    delivery.handover_code = _make_code()
    delivery.status = OrderDelivery.Status.OFFERED
    delivery.offered_at = timezone.now()
    delivery.save(update_fields=["handover_code", "status", "offered_at", "updated_at"])
    _alert_drivers(delivery)
    return delivery


def _alert_drivers(delivery):
    drivers = _eligible_drivers(delivery)
    if not drivers:
        _notify(
            delivery.order.seller,
            f"Order #{delivery.order_id} needs a driver, but none of your drivers can take it right now. Add another driver.",
            target=delivery.order,
            subject=f"Order #{delivery.order_id}: add a driver",
            link=f"/orders/{delivery.order_id}",
        )
        return
    for driver in drivers:
        offer, _ = DeliveryOffer.objects.update_or_create(
            delivery=delivery, driver=driver, defaults={"status": DeliveryOffer.Status.PENDING}
        )
        pay = driver_net(delivery.fee)
        _notify(
            driver.user,
            f"New delivery job: {delivery.pickup_area.name} to {delivery.dropoff_area.name}, you earn {pay:,.0f} naira. First to accept gets it.",
            target=delivery.order,
            subject="New delivery job. First to accept gets it",
            link="/driver/jobs",
        )


# --- driver actions --------------------------------------------------------------------------------


def _driver_for(user):
    profile = getattr(user, "driver_profile", None)
    if profile is None or not profile.is_approved:
        raise DispatchError("Only approved drivers can do this.", code="not_approved", status=403)
    return profile


@transaction.atomic
def accept_job(delivery_id, user):
    driver = _driver_for(user)
    delivery = OrderDelivery.objects.select_for_update().select_related("order", "order__buyer", "order__seller").get(pk=delivery_id)
    offer = DeliveryOffer.objects.filter(delivery=delivery, driver=driver).first()
    if offer is None or offer.status in (DeliveryOffer.Status.WITHDRAWN, DeliveryOffer.Status.DECLINED):
        raise DispatchError("This job is not available to you.", code="not_offered", status=404)
    if delivery.status != OrderDelivery.Status.OFFERED or delivery.driver_id is not None:
        raise DispatchError("Already accepted by another driver.", code="already_accepted", status=409)

    delivery.driver = driver
    delivery.status = OrderDelivery.Status.ACCEPTED
    delivery.accepted_at = timezone.now()
    delivery.save(update_fields=["driver", "status", "accepted_at", "updated_at"])
    offer.status = DeliveryOffer.Status.ACCEPTED
    offer.save(update_fields=["status", "updated_at"])
    DeliveryOffer.objects.filter(delivery=delivery, status=DeliveryOffer.Status.PENDING).exclude(pk=offer.pk).update(
        status=DeliveryOffer.Status.TAKEN
    )
    order = delivery.order
    _notify(
        order.seller,
        f"{driver.public_name} will deliver order #{order.id}. Hand the item to them when they arrive.",
        target=order,
        subject=f"Order #{order.id}: a driver accepted",
        link=f"/orders/{order.id}",
    )
    _notify(
        order.buyer,
        f"{driver.public_name} will deliver your order #{order.id}. Have your handover code ready, and only share it once you hold the item.",
        target=order,
        subject=f"Order #{order.id}: a driver is on the job",
        link=f"/orders/{order.id}",
    )
    return delivery


@transaction.atomic
def decline_job(delivery_id, user):
    driver = _driver_for(user)
    offer = DeliveryOffer.objects.select_for_update().filter(delivery_id=delivery_id, driver=driver).first()
    if offer is None or offer.status != DeliveryOffer.Status.PENDING:
        raise DispatchError("There is nothing to decline.", status=404)
    offer.status = DeliveryOffer.Status.DECLINED
    offer.save(update_fields=["status", "updated_at"])
    return offer


@transaction.atomic
def reassign(order, user, add_driver_ids=()):
    """The seller changed their mind about the driver (or wants more drivers), before pickup."""
    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.seller_id != user.id:
        raise DispatchError("Only the seller can change the driver.", status=403)
    delivery = OrderDelivery.objects.select_for_update().filter(order=order).first()
    if delivery is None or delivery.status not in (OrderDelivery.Status.OFFERED, OrderDelivery.Status.ACCEPTED):
        raise DispatchError("The driver can only be changed before the item is picked up.")
    options = ListingDelivery.objects.filter(listing_id=order.listing_id).first()
    if add_driver_ids and options is not None:
        for driver in DriverProfile.objects.filter(pk__in=add_driver_ids, status=DriverProfile.Status.APPROVED):
            options.drivers.add(driver)

    previous = delivery.driver
    if previous is not None:
        DeliveryOffer.objects.filter(delivery=delivery, driver=previous).update(status=DeliveryOffer.Status.WITHDRAWN)
        _notify(
            previous.user,
            f"The seller gave order #{order.id} to another driver, so you no longer need to deliver it.",
            target=order,
            subject=f"Order #{order.id}: job reassigned",
        )
    DeliveryOffer.objects.filter(delivery=delivery, status__in=[DeliveryOffer.Status.TAKEN, DeliveryOffer.Status.PENDING]).update(
        status=DeliveryOffer.Status.PENDING
    )
    delivery.driver = None
    delivery.status = OrderDelivery.Status.OFFERED
    delivery.accepted_at = None
    delivery.offered_at = timezone.now()
    delivery.nudged_at = None
    delivery.save(update_fields=["driver", "status", "accepted_at", "offered_at", "nudged_at", "updated_at"])
    _alert_drivers_excluding(delivery, previous)
    return delivery


def _alert_drivers_excluding(delivery, excluded):
    drivers = [d for d in _eligible_drivers(delivery) if excluded is None or d.pk != excluded.pk]
    if not drivers:
        _notify(
            delivery.order.seller,
            f"Order #{delivery.order_id} needs a driver. Add another driver who can take it.",
            target=delivery.order,
            subject=f"Order #{delivery.order_id}: add a driver",
            link=f"/orders/{delivery.order_id}",
        )
    for driver in drivers:
        DeliveryOffer.objects.update_or_create(delivery=delivery, driver=driver, defaults={"status": DeliveryOffer.Status.PENDING})
        _notify(
            driver.user,
            f"New delivery job: {delivery.pickup_area.name} to {delivery.dropoff_area.name}, you earn {driver_net(delivery.fee):,.0f} naira. First to accept gets it.",
            target=delivery.order,
            subject="New delivery job. First to accept gets it",
            link="/driver/jobs",
        )


@transaction.atomic
def mark_picked_up(delivery_id, user):
    driver = _driver_for(user)
    delivery = OrderDelivery.objects.select_for_update().select_related("order").get(pk=delivery_id)
    if delivery.driver_id != driver.pk:
        raise DispatchError("This is not your delivery.", status=403)
    if delivery.status != OrderDelivery.Status.ACCEPTED:
        raise DispatchError("This delivery cannot be marked as picked up right now.")
    order = Order.objects.select_for_update().get(pk=delivery.order_id)
    if order.status == OrderStatus.PAID_ESCROW:
        order.transition_to(OrderStatus.COURIER_ASSIGNED, actor=user, note="[auto] A driver accepted the delivery")
    if order.status == OrderStatus.COURIER_ASSIGNED:
        order.transition_to(OrderStatus.IN_TRANSIT, actor=user, note="Driver picked up the item")
    elif order.status != OrderStatus.IN_TRANSIT:
        raise DispatchError("This order can no longer be delivered (it may be disputed or refunded).")
    delivery.status = OrderDelivery.Status.PICKED_UP
    delivery.picked_up_at = timezone.now()
    delivery.save(update_fields=["status", "picked_up_at", "updated_at"])
    return delivery


def complete_delivery(delivery_id, user, code, photo_bytes, photo_type):
    """Driver hands over the item: needs the buyer's code and a photo. Pays out the seller and the driver."""
    driver = _driver_for(user)

    # Phase 1 commits on its own, so a wrong code is counted even though we then raise.
    with transaction.atomic():
        delivery = OrderDelivery.objects.select_for_update().get(pk=delivery_id)
        if delivery.driver_id != driver.pk:
            raise DispatchError("This is not your delivery.", status=403)
        if delivery.status != OrderDelivery.Status.PICKED_UP:
            raise DispatchError("Pick the item up first, then confirm delivery.")
        if delivery.code_attempts >= settings.HANDOVER_MAX_ATTEMPTS:
            raise DispatchError("Too many wrong codes. Contact Choropia support to continue.", code="code_locked", status=423)
        if not photo_bytes:
            raise DispatchError("Take a photo of the delivered item as proof.")
        right = secrets.compare_digest((code or "").strip().encode(), delivery.handover_code.encode())
        if not right:
            delivery.code_attempts += 1
            delivery.save(update_fields=["code_attempts", "updated_at"])
            left = max(settings.HANDOVER_MAX_ATTEMPTS - delivery.code_attempts, 0)
    if not right:
        raise DispatchError(f"That code is not right. {left} tries left.", code="wrong_code", status=400)
    return _finish_delivery(delivery_id, user, photo_bytes, photo_type)


@transaction.atomic
def _finish_delivery(delivery_id, user, photo_bytes, photo_type):
    from payments.services import release_escrow

    order_id = OrderDelivery.objects.values_list("order_id", flat=True).get(pk=delivery_id)
    order = Order.objects.select_for_update().get(pk=order_id)  # same lock order as the buyer's confirm
    delivery = OrderDelivery.objects.select_for_update().get(pk=delivery_id)
    if delivery.status != OrderDelivery.Status.PICKED_UP:
        raise DispatchError("This delivery was already completed or cancelled.", status=409)
    if order.status == OrderStatus.DISPUTED:
        raise DispatchError("This order is under dispute; Choropia support will resolve it.", code="disputed", status=409)
    if order.status != OrderStatus.IN_TRANSIT:
        raise DispatchError("This order is not in transit.")

    delivery.status = OrderDelivery.Status.DELIVERED
    delivery.delivered_at = timezone.now()
    delivery.proof_photo = photo_bytes
    delivery.proof_content_type = photo_type
    delivery.save(update_fields=["status", "delivered_at", "proof_photo", "proof_content_type", "updated_at"])

    order.transition_to(OrderStatus.DELIVERED, actor=user, note="Driver delivered the item (photo taken)")
    order.transition_to(OrderStatus.CONFIRMED, actor=user, note="[auto] The buyer gave the driver the handover code")
    order.transition_to(OrderStatus.COMPLETED, actor=user, note="[auto] Handover code confirmed; escrow released")
    release_escrow(order, auto=False)
    return delivery


# --- housekeeping -------------------------------------------------------------------------------


def cancel_for_order(order):
    """The order was refunded or cancelled: the delivery job goes with it and the drivers are told."""
    delivery = OrderDelivery.objects.filter(order=order).exclude(status__in=[OrderDelivery.Status.CANCELLED, OrderDelivery.Status.DELIVERED]).first()
    if delivery is None:
        return
    drivers = list(DriverProfile.objects.filter(offers__delivery=delivery, offers__status__in=[DeliveryOffer.Status.PENDING, DeliveryOffer.Status.ACCEPTED]))
    delivery.status = OrderDelivery.Status.CANCELLED
    delivery.save(update_fields=["status", "updated_at"])
    DeliveryOffer.objects.filter(delivery=delivery).exclude(status=DeliveryOffer.Status.DECLINED).update(status=DeliveryOffer.Status.WITHDRAWN)
    for driver in drivers:
        _notify(driver.user, f"Delivery job for order #{order.id} was cancelled.", target=order, subject=f"Order #{order.id}: delivery cancelled")


def nudge_stale_offers(now=None):
    """If nobody accepted within DISPATCH_NUDGE_HOURS, tell the seller to add more drivers (once)."""
    now = now or timezone.now()
    cutoff = now - timezone.timedelta(hours=settings.DISPATCH_NUDGE_HOURS)
    nudged = []
    for delivery in OrderDelivery.objects.filter(
        status=OrderDelivery.Status.OFFERED, offered_at__lte=cutoff, nudged_at__isnull=True
    ).select_related("order", "order__seller"):
        with transaction.atomic():
            fresh = OrderDelivery.objects.select_for_update().get(pk=delivery.pk)
            if fresh.status != OrderDelivery.Status.OFFERED or fresh.nudged_at is not None:
                continue
            fresh.nudged_at = now
            fresh.save(update_fields=["nudged_at", "updated_at"])
            _notify(
                delivery.order.seller,
                f"No driver has accepted order #{delivery.order_id} yet. Add another driver so it gets picked up.",
                target=delivery.order,
                subject=f"Order #{delivery.order_id}: still waiting for a driver",
                link=f"/orders/{delivery.order_id}",
            )
            nudged.append(delivery.pk)
    return nudged
