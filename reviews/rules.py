"""Who may be reviewed, and by whom.

Reviews work like a ride rating: the BUYER rates the SELLER, once per order, after the money has moved (the buyer confirmed the
item, or the order is complete). Only sellers who post consistently can be rated (at least REVIEW_MIN_LISTINGS listings), so a
one-off poster is never judged. The same rules apply to verified and unverified sellers; the rating just shows a "Verified" badge
next to verified ones."""
from django.conf import settings
from django.db.models import Avg, Count, F

from accounts.models import is_verified_seller
from listings.models import Listing
from orders.models import Order

REVIEWABLE_STATUSES = (Order.Status.CONFIRMED, Order.Status.COMPLETED)


def listing_count(user):
    return Listing.objects.filter(owner=user).exclude(status=Listing.Status.REMOVED).count()


def seller_qualifies(user):
    return listing_count(user) >= settings.REVIEW_MIN_LISTINGS


def check(order, reviewer):
    """(allowed, reason). `reason` is plain language for the screen when not allowed."""
    from .models import Review

    if reviewer.id != order.buyer_id:
        return False, "Only the buyer can review a seller."
    if order.status not in REVIEWABLE_STATUSES:
        return False, "You can review once you have confirmed that the item arrived."
    if not seller_qualifies(order.seller):
        return False, "This seller does not have enough listings to be reviewed yet."
    if Review.objects.filter(order=order, reviewer=reviewer).exists():
        return False, "You have already reviewed this order."
    return True, ""


def summary(user):
    """The public rating of a seller, or `eligible: false` when they have not posted enough to be rated."""
    from .models import Review

    if not seller_qualifies(user):
        return {"eligible": False, "average": None, "count": 0, "verified": is_verified_seller(user)}
    stats = Review.objects.filter(reviewee=user, reviewer=F("order__buyer")).aggregate(avg=Avg("rating"), n=Count("id"))
    average = round(float(stats["avg"]), 1) if stats["avg"] is not None else None
    return {"eligible": True, "average": average, "count": stats["n"], "verified": is_verified_seller(user)}

