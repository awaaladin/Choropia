"""The "protected through Choropia escrow" figure shown on the website: a round milestone, never an exact total.

Showing every kobo (or a single buyer's own order) would say little and reveal business numbers. Instead the public figure steps
up only when the platform passes a threshold: 100,000, 500,000, 1 million, 5 million, 10 million, and so on."""
from decimal import Decimal

from django.core.cache import cache
from django.db.models import Sum

from .models import Payment

CACHE_KEY = "escrow-milestone"
CACHE_SECONDS = 600
# 100k, 500k, 1M, 5M, 10M, 50M, 100M, ... (alternating x5 and x2 steps, continuing for ever)
FIRST = 100_000


def thresholds():
    value = FIRST
    while True:
        yield value
        yield value * 5
        value *= 10


def highest_milestone(total):
    """The largest threshold not above `total`, or 0 when none has been reached yet."""
    reached = 0
    for step in thresholds():
        if step > total:
            break
        reached = step
    return reached


def short_label(amount):
    if amount >= 1_000_000_000:
        return f"\u20a6{amount // 1_000_000_000:,}B"
    if amount >= 1_000_000:
        return f"\u20a6{amount // 1_000_000:,}M"
    return f"\u20a6{amount:,}"


def protected_total():
    return (
        Payment.objects.filter(status__in=[Payment.Status.PAID_HELD, Payment.Status.RELEASED]).aggregate(total=Sum("amount"))["total"]
        or Decimal("0")
    )


def current():
    data = cache.get(CACHE_KEY)
    if data is None:
        reached = highest_milestone(int(protected_total()))
        data = {"milestone": reached, "label": short_label(reached) if reached else ""}
        cache.set(CACHE_KEY, data, CACHE_SECONDS)
    return data
