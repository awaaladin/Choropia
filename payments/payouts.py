"""
Automatic seller payouts, and Choropia's commission.

When a buyer confirms receipt (or the escrow window passes) the order's payment is RELEASED. This
module then pays the seller by bank transfer (Paystack Transfers) and keeps a commission:

    buyer paid (gross)  =  commission (PLATFORM_COMMISSION_PERCENT, default 5%)  +  sent to seller (net)

Money going OUT is the dangerous direction, so the rules here are strict:

* One Payout per Payment (database unique), so a release can never pay a seller twice.
* The transfer reference is saved and the payout marked PROCESSING *before* the network call is
  made, and the call happens after the database transaction has committed. A crash or timeout can
  therefore never leave us unable to find out what happened: the reference is looked up at Paystack.
* A reference is never reused after a failure; a retry gets a fresh one, and only after Paystack has
  confirmed the previous attempt did not go through.
* An unknown outcome (timeout) is never retried blindly; `reconcile_payout` asks Paystack first.
* PAYOUTS_ENABLED=false stops all transfers; PAYOUT_MAX_NGN holds very large payouts for a person.

The seller's account number is held by Paystack as a "transfer recipient"; we keep only the last
four digits and the account name the bank returned.
"""
import logging
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from .models import Payment, Payout, PayoutAccount
from .naming import is_ours, make_transfer_reference
from .paystack import PaystackClient, PaystackError

logger = logging.getLogger(__name__)

TWO_PLACES = Decimal("0.01")
BANKS_CACHE_KEY = "paystack-banks-v1"
BANKS_CACHE_SECONDS = 24 * 3600
# How long a transfer may sit in PROCESSING with no answer before we ask Paystack what happened.
RECONCILE_AFTER = timedelta(minutes=5)


def _paystack():
    return PaystackClient()


# --- money maths ----------------------------------------------------------------------------


def commission_split(gross, percent=None):
    """(commission, net) for a gross amount. Commission is rounded to the kobo (half up) and the
    seller gets exactly the remainder, so commission + net always equals gross."""
    percent = settings.PLATFORM_COMMISSION_PERCENT if percent is None else Decimal(percent)
    gross = Decimal(gross).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    commission = (gross * percent / Decimal(100)).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    return commission, gross - commission


# --- creating a payout (called when escrow is released) -------------------------------------


def create_payout(payment):
    """Records what the seller is owed. Safe to call twice; the second call returns the first."""
    existing = Payout.objects.filter(payment=payment).first()
    if existing:
        return existing

    seller = payment.order.seller
    commission, net = commission_split(payment.amount)
    has_account = PayoutAccount.objects.filter(user=seller).exists()
    return Payout.objects.create(
        payment=payment,
        seller=seller,
        gross_amount=payment.amount,
        commission_rate=settings.PLATFORM_COMMISSION_PERCENT,
        commission_amount=commission,
        net_amount=net,
        status=Payout.Status.PENDING if has_account else Payout.Status.AWAITING_ACCOUNT,
    )


def release_hook(payment):
    """Called from release_escrow inside the caller's transaction. Records the payout, then sends
    the transfer only once that transaction has committed (so a rollback can never leave money sent
    for a release that didn't happen)."""
    payout = create_payout(payment)
    transaction.on_commit(lambda: process_payout_safely(payout.pk))
    return payout


# --- sending ---------------------------------------------------------------------------------


def _attention(payout, reason):
    payout.status = Payout.Status.NEEDS_ATTENTION
    payout.failure_reason = reason[:500]
    payout.save(update_fields=["status", "failure_reason", "updated_at"])
    logger.error("Payout %s needs a person: %s", payout.pk, reason)
    return payout


def _retry_or_attention(payout, reason):
    """The transfer definitely did not go through. Queue another attempt, or give up to a person."""
    payout.failure_reason = reason[:500]
    if payout.attempts >= settings.PAYOUT_MAX_ATTEMPTS:
        payout.status = Payout.Status.NEEDS_ATTENTION
        logger.error("Payout %s gave up after %s attempts: %s", payout.pk, payout.attempts, reason)
    else:
        payout.status = Payout.Status.PENDING
        logger.warning("Payout %s will be retried (attempt %s): %s", payout.pk, payout.attempts, reason)
    payout.save(update_fields=["status", "failure_reason", "updated_at"])
    return payout


def _succeed(payout, transfer_code=""):
    payout.status = Payout.Status.SUCCESS
    payout.completed_at = payout.completed_at or timezone.now()
    payout.failure_reason = ""
    if transfer_code:
        payout.paystack_transfer_code = transfer_code
    payout.save(update_fields=["status", "completed_at", "failure_reason", "paystack_transfer_code", "updated_at"])
    Payment.objects.filter(pk=payout.payment_id).update(transfer_reference=payout.transfer_reference or "")
    logger.info("Payout %s paid: NGN %s to %s", payout.pk, payout.net_amount, payout.account_name)
    return payout


def process_payout_safely(payout_id):
    """For hooks and schedulers: never raises, so it can't break the request that triggered it."""
    try:
        return process_payout(payout_id)
    except Exception:  # noqa: BLE001
        logger.exception("Unexpected error processing payout %s", payout_id)
        return None


def process_payout(payout_id):
    """Sends the transfer if, and only if, it is safe to. Idempotent."""
    if not settings.PAYOUTS_ENABLED:
        return None

    with transaction.atomic():
        payout = Payout.objects.select_for_update().select_related("payment__order").get(pk=payout_id)
        if payout.status not in (Payout.Status.PENDING, Payout.Status.AWAITING_ACCOUNT):
            return payout  # already sent, in flight, paid, or parked for a person
        if payout.payment.status != Payment.Status.RELEASED:
            return payout  # never pay out money that has not been released

        account = PayoutAccount.objects.filter(user_id=payout.seller_id).first()
        if account is None:
            if payout.status != Payout.Status.AWAITING_ACCOUNT:
                payout.status = Payout.Status.AWAITING_ACCOUNT
                payout.save(update_fields=["status", "updated_at"])
            return payout
        if payout.net_amount > settings.PAYOUT_MAX_NGN:
            return _attention(payout, f"NGN {payout.net_amount} is above the automatic limit of NGN {settings.PAYOUT_MAX_NGN}.")
        if payout.net_amount <= 0:
            return _attention(payout, "Nothing to pay out after commission.")

        # Reserve the reference and mark PROCESSING *before* talking to Paystack.
        reference = make_transfer_reference()
        payout.transfer_reference = reference
        payout.transfer_references = [*payout.transfer_references, reference]
        payout.status = Payout.Status.PROCESSING
        payout.attempts += 1
        payout.initiated_at = timezone.now()
        payout.bank_name, payout.account_last4, payout.account_name = account.bank_name, account.account_last4, account.account_name
        payout.save()
        recipient_code, amount, order_id = account.recipient_code, payout.net_amount, payout.payment.order_id

    # Outside the transaction: the network call.
    try:
        data = _paystack().initiate_transfer(
            amount=amount, recipient_code=recipient_code, reference=reference, reason=f"Choropia order #{order_id} payout"
        )
    except PaystackError as exc:
        return _after_transfer_error(payout.pk, exc)
    return _apply_transfer_data(payout.pk, data)


def _after_transfer_error(payout_id, exc):
    payout = Payout.objects.get(pk=payout_id)
    if exc.http_status is None:
        # Timeout / network: we do NOT know whether Paystack received it. Leave it PROCESSING;
        # reconcile_payout asks Paystack about this exact reference before anything is retried.
        logger.warning("Payout %s: outcome unknown (%s); will reconcile", payout.pk, exc)
        payout.failure_reason = f"Waiting to confirm with Paystack: {exc}"[:500]
        payout.save(update_fields=["failure_reason", "updated_at"])
        return payout
    if exc.http_status in (401, 403):
        return _attention(payout, f"Paystack refused the request ({exc.http_status}): {exc}. Check the key and the transfer permissions.")
    # Any other HTTP error is a definite rejection: nothing was created at Paystack (for example
    # "balance is not enough", or an invalid recipient). Try again later.
    return _retry_or_attention(payout, str(exc))


def _apply_transfer_data(payout_id, data):
    payout = Payout.objects.get(pk=payout_id)
    status = (data.get("status") or "").lower()
    code = data.get("transfer_code", "") or ""
    if code:
        payout.paystack_transfer_code = code
        payout.save(update_fields=["paystack_transfer_code", "updated_at"])
    if status == "success":
        return _succeed(payout, code)
    if status in ("pending", "received", "queued", "processing", ""):
        return payout  # PROCESSING; the transfer.success webhook (or reconcile) completes it
    if status == "otp":
        return _attention(
            payout,
            "Paystack is waiting for OTP approval. Turn off 'Confirm transfers before sending' "
            "(Paystack Settings > Preferences) and finalize this transfer once in the dashboard.",
        )
    return _retry_or_attention(payout, f"Transfer {status or 'failed'}: {data.get('reason') or data.get('message') or ''}".strip())


# --- Paystack events and reconciliation -----------------------------------------------------


def apply_transfer_event(event, data):
    """Applies transfer.success / transfer.failed / transfer.reversed from the webhook."""
    reference = (data or {}).get("reference", "")
    if not is_ours(reference):
        return None
    # Only the CURRENT attempt's reference matches. An event for an older attempt (which we only
    # supersede after Paystack confirmed it failed) is deliberately ignored.
    payout = Payout.objects.filter(transfer_reference=reference).first()
    if payout is None:
        logger.warning("Transfer event %s for unknown or superseded reference %s", event, reference)
        return None

    with transaction.atomic():
        payout = Payout.objects.select_for_update().get(pk=payout.pk)
        if event == "transfer.success":
            if payout.status != Payout.Status.SUCCESS:
                _succeed(payout, (data or {}).get("transfer_code", ""))
        elif event == "transfer.failed":
            if payout.status == Payout.Status.PROCESSING:
                _retry_or_attention(payout, f"Transfer failed: {(data or {}).get('reason') or 'bank rejected it'}")
        elif event == "transfer.reversed":
            _attention(payout, "The bank returned this transfer after sending it. Check the account details with the seller.")
    return payout


def reconcile_payout(payout_id):
    """Asks Paystack what really happened to a payout that has been PROCESSING for a while."""
    payout = Payout.objects.get(pk=payout_id)
    if payout.status != Payout.Status.PROCESSING or not payout.transfer_reference:
        return payout
    try:
        data = _paystack().verify_transfer(payout.transfer_reference)
    except PaystackError as exc:
        if exc.http_status == 404:
            # Paystack has never heard of this reference, so nothing was sent. Safe to try again
            # (with a new reference, which process_payout generates).
            return _retry_or_attention(payout, "Paystack had no record of the transfer; retrying.")
        logger.warning("Could not reconcile payout %s: %s", payout.pk, exc)
        return payout
    status = (data.get("status") or "").lower()
    if status == "success":
        return _succeed(payout, data.get("transfer_code", ""))
    if status in ("failed", "reversed"):
        if status == "reversed":
            return _attention(payout, "The bank returned this transfer. Check the account details with the seller.")
        return _retry_or_attention(payout, f"Transfer failed: {data.get('reason') or 'bank rejected it'}")
    if status == "otp":
        return _apply_transfer_data(payout.pk, data)
    return payout  # still genuinely in progress


def process_pending_payouts(limit=25):
    """Run by the scheduler: sends queued payouts, picks up sellers who have since added a bank
    account, and reconciles transfers whose outcome we never heard."""
    if not settings.PAYOUTS_ENABLED:
        return {"enabled": False}
    sent, reconciled = [], []

    stale = timezone.now() - RECONCILE_AFTER
    for payout in Payout.objects.filter(status=Payout.Status.PROCESSING, initiated_at__lte=stale)[:limit]:
        reconcile_payout(payout.pk)
        reconciled.append(payout.pk)

    waiting = Payout.objects.filter(status__in=[Payout.Status.PENDING, Payout.Status.AWAITING_ACCOUNT]).order_by("created_at")
    for payout in waiting[:limit]:
        result = process_payout_safely(payout.pk)
        if result is not None and result.status in (Payout.Status.PROCESSING, Payout.Status.SUCCESS):
            sent.append(payout.pk)
    return {"enabled": True, "sent": sent, "reconciled": reconciled}


# --- sellers' bank accounts -----------------------------------------------------------------


def nigerian_banks():
    """[{code, name}], cached for a day."""
    try:
        banks = cache.get(BANKS_CACHE_KEY)
    except Exception:  # noqa: BLE001 - a cache outage must not take the bank list down
        banks = None
    if banks is None:
        banks = sorted(
            ({"code": b["code"], "name": b["name"]} for b in _paystack().list_banks() if b.get("code") and b.get("name")),
            key=lambda b: b["name"].lower(),
        )
        try:
            cache.set(BANKS_CACHE_KEY, banks, BANKS_CACHE_SECONDS)
        except Exception:  # noqa: BLE001
            logger.warning("Could not cache the bank list")
    return banks


def save_payout_account(user, bank_code, account_number):
    """Verifies the account with the bank, registers it as a Paystack recipient, and stores it.
    Then immediately releases any payouts that were waiting for it."""
    bank = next((b for b in nigerian_banks() if b["code"] == bank_code), None)
    if bank is None:
        raise PaystackError("Choose a bank from the list.")
    resolved = _paystack().resolve_account(account_number, bank_code)
    account_name = resolved.get("account_name", "").strip()
    if not account_name:
        raise PaystackError("The bank did not return a name for that account number.")
    recipient = _paystack().create_recipient(account_name, account_number, bank_code)

    account, _ = PayoutAccount.objects.update_or_create(
        user=user,
        defaults={
            "bank_code": bank_code,
            "bank_name": bank["name"],
            "account_last4": account_number[-4:],
            "account_name": account_name,
            "recipient_code": recipient["recipient_code"],
        },
    )
    for payout_id in Payout.objects.filter(
        seller=user, status__in=[Payout.Status.AWAITING_ACCOUNT, Payout.Status.PENDING]
    ).values_list("pk", flat=True):
        transaction.on_commit(lambda pid=payout_id: process_payout_safely(pid))
    return account


# --- one entry point for Choropia's Paystack events ------------------------------------------


def handle_choropia_event(payload):
    """Everything Paystack tells us about Choropia's money, from the router or the direct webhook."""
    from .services import confirm_paystack_payment

    event = payload.get("event")
    data = payload.get("data") or {}
    reference = data.get("reference", "")
    if not is_ours(reference):
        return
    if event == "charge.success":
        confirm_paystack_payment(reference, data, raw_payload=payload)
    elif event in ("transfer.success", "transfer.failed", "transfer.reversed"):
        apply_transfer_event(event, data)
