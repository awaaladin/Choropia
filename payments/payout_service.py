"""
How a released payout reaches the person it's owed to.

    get_payout_service().submit(payout)

ManualPayoutService (the default today)
    Paystack Transfers is not enabled on Choropia's account yet (it needs the Registered Business / KYC upgrade).
    A payout is left in the staff panel's queue (Staff → Payouts → Waiting) and staff are alerted by email. Staff pay
    it from the bank app and press "Mark as paid", which records who paid it and the bank reference
    (payouts.mark_paid_manually) and writes a PAYOUT_SENT ledger entry.

PaystackTransferPayoutService
    ┌────────────────────────────────────────────────────────────────────────────────────────────────┐
    │ SWAP-IN POINT. Turn on after Paystack enables Transfers: set PAYOUTS_ENABLED=true.             │
    │ The transfer code itself already exists in payments/payouts.py (process_payout: reference      │
    │ reserved before the call, reconcile on timeout, never pays twice) and is unit-tested against   │
    │ mocks, but it has never run against live Transfers. Before enabling: send one small test      │
    │ payout, watch the transfer.success webhook arrive, then enable for everyone.                   │
    └────────────────────────────────────────────────────────────────────────────────────────────────┘
"""
import logging
from abc import ABC, abstractmethod

from django.conf import settings
from django.db import transaction

logger = logging.getLogger(__name__)


class PayoutService(ABC):
    name = ""
    automatic = False

    @abstractmethod
    def submit(self, payout) -> None:
        """Called inside the release transaction, right after the Payout row is created. Must not send money before
        that transaction commits."""


class ManualPayoutService(PayoutService):
    name = "manual"
    automatic = False

    def submit(self, payout):
        from notifications import staff_alerts

        who = "driver" if payout.kind == "driver" else "seller"
        lines = [
            f"Pay the {who} {payout.seller.get_full_name() or payout.seller.email} {staff_alerts.money(payout.net_amount)} "
            f"for order #{payout.payment.order_id}"
            + (f" (Choropia keeps {staff_alerts.money(payout.commission_amount)})." if payout.kind != "driver" else "."),
            "Then press Mark as paid on the payout page and enter the bank's reference.",
        ]
        staff_alerts.alert(f"Pay out order #{payout.payment.order_id}", "Money to hand over", lines, f"/staff/payouts/{payout.pk}/")


class PaystackTransferPayoutService(PayoutService):
    name = "paystack_transfer"
    automatic = True

    def submit(self, payout):
        from . import payouts

        payout_id = payout.pk
        transaction.on_commit(lambda: payouts.process_payout_safely(payout_id))


def get_payout_service() -> PayoutService:
    return PaystackTransferPayoutService() if settings.PAYOUTS_ENABLED else ManualPayoutService()
