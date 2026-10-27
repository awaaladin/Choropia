"""What each person is allowed to see about a delivery.

The rule behind every choice here: contact details and the exact address stay hidden until money
is in escrow AND a driver has accepted, and only the people who need them see them. Before that,
the only way to reach each other is in-app chat. This is what stops a deal leaking off the platform."""
from .models import DeliveryOffer, DriverProfile, OrderDelivery
from .services import driver_net


def _area(area):
    return {"id": area.id, "name": area.name}


def _person(user):
    return {"name": user.get_full_name(), "phone": user.phone_number or ""}


def delivery_payload(delivery, user):
    """The delivery as `user` (buyer, seller or the assigned driver) may see it."""
    order = delivery.order
    is_buyer = user.id == order.buyer_id
    is_seller = user.id == order.seller_id
    driver = delivery.driver
    is_driver = driver is not None and driver.user_id == user.id
    assigned = delivery.status in (OrderDelivery.Status.ACCEPTED, OrderDelivery.Status.PICKED_UP, OrderDelivery.Status.DELIVERED)

    data = {
        "id": delivery.id,
        "order": order.id,
        "status": delivery.status,
        "status_label": delivery.get_status_display(),
        "pickup_area": _area(delivery.pickup_area),
        "dropoff_area": _area(delivery.dropoff_area),
        "payer": delivery.payer,
        "fee": str(delivery.fee),
        "buyer_share": str(delivery.buyer_share),
        "seller_share": str(delivery.seller_share),
        "driver": None,
    }
    if assigned and (is_buyer or is_seller):
        data["driver"] = {
            "name": driver.public_name,
            "vehicle_type": driver.get_vehicle_type_display(),
            "plate_number": driver.plate_number,
            # Contact details appear only once the driver has the job, so a deal cannot be taken off the site.
            "phone": driver.phone,
            "whatsapp": driver.whatsapp,
        }
    if is_buyer:
        data["handover_code"] = delivery.handover_code if delivery.status in (
            OrderDelivery.Status.OFFERED, OrderDelivery.Status.ACCEPTED, OrderDelivery.Status.PICKED_UP
        ) else ""
        data["dropoff_note"] = delivery.dropoff_note
        data["can_cancel_choice"] = delivery.status == OrderDelivery.Status.AWAITING_PAYMENT
    if is_seller:
        data["can_reassign"] = delivery.status in (OrderDelivery.Status.OFFERED, OrderDelivery.Status.ACCEPTED)
        data["drivers_notified"] = delivery.offers.exclude(status=DeliveryOffer.Status.WITHDRAWN).count()
    if is_driver:
        data["you_earn"] = str(driver_net(delivery.fee))
        data["listing_title"] = order.listing.title
        data["pickup"] = _person(order.seller)
        # The buyer's exact address and phone are for the assigned driver only.
        data["dropoff"] = {**_person(order.buyer), "note": delivery.dropoff_note}
        data["can_pick_up"] = delivery.status == OrderDelivery.Status.ACCEPTED
        data["can_deliver"] = delivery.status == OrderDelivery.Status.PICKED_UP
    return data


def job_card(offer):
    """A job alert for a driver who has not accepted yet: route and pay only, no addresses or contacts."""
    delivery = offer.delivery
    taken = offer.status == DeliveryOffer.Status.TAKEN or (
        delivery.driver_id is not None and delivery.driver_id != offer.driver_id
    )
    return {
        "id": delivery.id,
        "order": delivery.order_id,
        "listing_title": delivery.order.listing.title,
        "pickup_area": _area(delivery.pickup_area),
        "dropoff_area": _area(delivery.dropoff_area),
        "you_earn": str(driver_net(delivery.fee)),
        "offer_status": offer.status,
        "state": "already_accepted" if taken else offer.status,
        "delivery_status": delivery.status,
        "created_at": delivery.offered_at,
    }


def public_driver(driver, routes):
    return {
        "id": driver.id,
        "name": driver.public_name,
        "vehicle_type": driver.get_vehicle_type_display(),
        "routes": [
            {"id": r.id, "from_area": _area(r.from_area), "to_area": _area(r.to_area), "price": str(r.price)}
            for r in routes
        ],
    }


def driver_me(profile):
    from .models import DriverDocument

    uploaded = set(profile.documents.values_list("kind", flat=True))
    return {
        "id": profile.id,
        "status": profile.status,
        "status_label": profile.get_status_display(),
        "review_note": profile.review_note if profile.status in (DriverProfile.Status.REJECTED, DriverProfile.Status.SUSPENDED) else "",
        "full_name": profile.full_name,
        "phone": profile.phone,
        "whatsapp": profile.whatsapp,
        "vehicle_type": profile.vehicle_type,
        "plate_number": profile.plate_number,
        "guarantor_name": profile.guarantor_name,
        "guarantor_phone": profile.guarantor_phone,
        "available": profile.available,
        "documents": [
            {"kind": kind.value, "label": kind.label, "uploaded": kind.value in uploaded}
            for kind in DriverDocument.REQUIRED
        ],
        "documents_complete": all(k.value in uploaded for k in DriverDocument.REQUIRED),
    }
