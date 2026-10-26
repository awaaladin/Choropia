from django.conf import settings
from django.db import models

from common.models import TimeStampedModel
from orders.models import Order


class Payment(TimeStampedModel):
    class Status(models.TextChoices):
        INITIALIZED = "initialized", "Initialized"
        PAID_HELD = "paid_held", "Paid — held in escrow"
        RELEASED = "released", "Released to seller"
        REFUNDED = "refunded", "Refunded to buyer"
        FAILED = "failed", "Failed"
        REFUND_PENDING = "refund_pending", "Refund pending (item was no longer available)"

    class Provider(models.TextChoices):
        PAYSTACK = "paystack", "Paystack"
        GAXTRON = "gaxtron", "Gaxtron (crypto)"

    order = models.OneToOneField(Order, on_delete=models.PROTECT, related_name="payment")
    reference = models.CharField(max_length=100, unique=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)  # order price, in NGN
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.INITIALIZED)
    provider = models.CharField(max_length=20, choices=Provider.choices, default=Provider.PAYSTACK)

    authorization_url = models.URLField(blank=True)  # the provider's hosted checkout page
    paid_at = models.DateTimeField(null=True, blank=True)
    released_at = models.DateTimeField(null=True, blank=True)
    refunded_at = models.DateTimeField(null=True, blank=True)
    auto_released = models.BooleanField(default=False)

    # Gaxtron settles in crypto (ETH-only as of this integration), converted from `amount` (NGN)
    # at checkout time — see payments/gaxtron.py.
    gaxtron_payment_id = models.PositiveIntegerField(null=True, blank=True, unique=True)
    crypto_amount = models.DecimalField(max_digits=36, decimal_places=18, null=True, blank=True)
    crypto_currency = models.CharField(max_length=10, blank=True, default="ETH")
    wallet_address = models.CharField(max_length=64, blank=True)
    tx_hash = models.CharField(max_length=100, blank=True)

    # Paystack's own id for the successful transaction (shown in its dashboard as "Transaction ID").
    paystack_transaction_id = models.CharField(max_length=40, blank=True)

    transfer_reference = models.CharField(max_length=100, blank=True)
    raw_webhook_payload = models.JSONField(null=True, blank=True)

    def __str__(self):
        return f"Payment<{self.reference}> {self.status}"


class PayoutAccount(TimeStampedModel):
    """Where a seller is paid. Paystack keeps the full account number (as a "transfer recipient");
    we store only the last four digits and the name the bank returned, which is all the app needs
    to show "GTBank ••••1234, ADA OBI" back to the seller."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="payout_account")
    bank_code = models.CharField(max_length=20)
    bank_name = models.CharField(max_length=100)
    account_last4 = models.CharField(max_length=4)
    account_name = models.CharField(max_length=150)  # as resolved by the bank
    recipient_code = models.CharField(max_length=50)  # Paystack's id for this account

    def __str__(self):
        return f"{self.bank_name} ••••{self.account_last4} ({self.user_id})"


class Payout(TimeStampedModel):
    """The seller's share of one released payment, and Choropia's commission on it.

    gross_amount (what the buyer paid) = commission_amount (Choropia's cut) + net_amount (sent to
    the seller). One payout per payment, so a release can never pay a seller twice."""

    class Status(models.TextChoices):
        AWAITING_ACCOUNT = "awaiting_account", "Waiting for seller's bank account"
        PENDING = "pending", "Queued"
        PROCESSING = "processing", "Transfer sent to the bank"
        SUCCESS = "success", "Paid"
        NEEDS_ATTENTION = "needs_attention", "Needs a person"

    payment = models.OneToOneField(Payment, on_delete=models.PROTECT, related_name="payout")
    seller = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="payouts")

    gross_amount = models.DecimalField(max_digits=12, decimal_places=2)
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2)  # percent, as at release time
    commission_amount = models.DecimalField(max_digits=12, decimal_places=2)
    net_amount = models.DecimalField(max_digits=12, decimal_places=2)

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    failure_reason = models.TextField(blank=True)

    # The reference of the current/last transfer, and every reference ever used (audit trail).
    transfer_reference = models.CharField(max_length=60, unique=True, null=True, blank=True)
    transfer_references = models.JSONField(default=list, blank=True)
    paystack_transfer_code = models.CharField(max_length=40, blank=True)

    # Snapshot of where it was sent, in case the seller later changes their account.
    bank_name = models.CharField(max_length=100, blank=True)
    account_last4 = models.CharField(max_length=4, blank=True)
    account_name = models.CharField(max_length=150, blank=True)

    initiated_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Payout<{self.payment_id}> {self.status} NGN {self.net_amount}"
