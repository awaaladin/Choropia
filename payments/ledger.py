"""Writes to the append-only escrow ledger (payments.models.LedgerEntry). Every function is idempotent."""
import logging

from .models import LedgerEntry, Payment
from .paystack import to_kobo

logger = logging.getLogger(__name__)
K = LedgerEntry.Kind


def record(key, kind, amount_kobo, *, payment=None, order=None, payout=None, reference="", note=""):
    entry, created = LedgerEntry.objects.get_or_create(
        key=key,
        defaults={
            "kind": kind,
            "amount_kobo": int(amount_kobo),
            "payment": payment,
            "order": order if order is not None else getattr(payment, "order", None),
            "payout": payout,
            "reference": reference or getattr(payment, "reference", ""),
            "note": note[:300],
        },
    )
    return entry


def held(payment):
    return record(f"held:{payment.pk}", K.HELD, to_kobo(payment.amount), payment=payment)


def received_for_refund(payment, note=""):
    return record(f"received_for_refund:{payment.pk}", K.RECEIVED_FOR_REFUND, to_kobo(payment.amount), payment=payment, note=note)


def refunded(payment):
    return record(f"refunded:{payment.pk}", K.REFUNDED, -to_kobo(payment.amount), payment=payment)


def released(payment, seller_payout, driver_payout=None):
    """Splits the held amount into what each party is owed. Anything not allocated is recorded, never hidden."""
    allocated = 0
    rows = [
        (K.SELLER_PAYABLE, seller_payout.net_amount, seller_payout),
        (K.PLATFORM_FEE, seller_payout.commission_amount, seller_payout),
    ]
    if driver_payout is not None:
        rows += [(K.DRIVER_PAYABLE, driver_payout.net_amount, driver_payout), (K.DRIVER_FEE, driver_payout.commission_amount, driver_payout)]
    for kind, amount, payout in rows:
        kobo = to_kobo(amount)
        allocated += kobo
        record(f"{kind}:{payment.pk}", kind, -kobo, payment=payment, payout=payout)
    leftover = to_kobo(payment.amount) - allocated
    if leftover:
        record(f"unallocated:{payment.pk}", K.UNALLOCATED, -leftover, payment=payment,
               note="Held money not allocated to anyone on release; staff to settle")
        logger.warning("Payment %s released with %s kobo unallocated", payment.reference, leftover)


def payout_sent(payout, reference=""):
    return record(f"payout_sent:{payout.pk}", K.PAYOUT_SENT, -to_kobo(payout.net_amount), payment=payout.payment,
                  payout=payout, reference=reference or payout.transfer_reference or payout.manual_reference or "")


def balance_kobo(payment):
    """Escrow balance still held for a payment: held + allocations (should be 0 once released or refunded)."""
    from django.db.models import Sum

    escrow_kinds = [K.HELD, K.RECEIVED_FOR_REFUND, K.SELLER_PAYABLE, K.PLATFORM_FEE, K.DRIVER_PAYABLE, K.DRIVER_FEE,
                    K.UNALLOCATED, K.REFUNDED]
    return LedgerEntry.objects.filter(payment=payment, kind__in=escrow_kinds).aggregate(s=Sum("amount_kobo"))["s"] or 0


__all__ = ["record", "held", "received_for_refund", "refunded", "released", "payout_sent", "balance_kobo", "Payment"]
