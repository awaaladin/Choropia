"""
Every email Choropia sends goes through here.

Rules this module enforces:
* An email problem (bad SMTP login, provider outage, unverified sending domain) can NEVER fail the
  request that triggered it: `send_email` logs and returns False instead of raising.
* Event emails are sent only AFTER the database transaction commits, so a rolled-back payment or
  order never produces a "payment received" email.
* HTML is rendered with Django's autoescaping (listing titles and names are user input), and
  subjects have newlines stripped (no header injection).
* Logs name the template and a masked address, never the full recipient or any code or link.

Delivery is Resend over SMTP (see EMAIL_* in settings). Resend only delivers from an address on a
domain verified in the Resend dashboard; DEFAULT_FROM_EMAIL must be on that domain.
"""
import logging
from decimal import Decimal
from html import unescape

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)


def naira(amount) -> str:
    return "₦{:,.2f}".format(Decimal(amount))


def _mask(address: str) -> str:
    name, _, domain = (address or "").partition("@")
    return f"{name[:1]}***@{domain}"


def _base_context() -> dict:
    return {
        "brand": "Choropia",
        "site_url": settings.CHOROPIA_SITE_URL.rstrip("/"),
        "year": timezone.now().year,
        "support_email": settings.SUPPORT_EMAIL,
    }


def _plain_text(html: str) -> str:
    """The text alternative: the HTML with tags removed, entities decoded (so a link keeps its real "&")
    and whitespace tidied. URLs are printed in the body of every template, so links survive."""
    lines = (" ".join(line.split()) for line in unescape(strip_tags(html)).splitlines())
    return "\n".join(line for line in lines if line)


def send_email(to: str, subject: str, template: str, context: dict | None = None) -> bool:
    """Renders emails/<template>.html and sends it. Never raises."""
    if not to:
        return False
    try:
        html = render_to_string(f"emails/{template}.html", {**_base_context(), **(context or {})})
        message = EmailMultiAlternatives(
            subject=" ".join(subject.split()),
            body=_plain_text(html),
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[to],
        )
        message.attach_alternative(html, "text/html")
        message.send(fail_silently=False)
        logger.info("Sent the %s email to %s", template, _mask(to))
        return True
    except Exception:  # noqa: BLE001 - email trouble must never break the caller
        logger.exception("Could not send the %s email to %s", template, _mask(to))
        return False


def send_email_after_commit(to: str, subject: str, template: str, context: dict | None = None) -> None:
    transaction.on_commit(lambda: send_email(to, subject, template, context))


def _display_name(user) -> str:
    return (user.first_name or "").strip() or "there"


# --- accounts -------------------------------------------------------------------------------


def send_welcome(user, code: str) -> None:
    send_email_after_commit(
        user.email,
        "Welcome to Choropia: confirm your email",
        "welcome",
        {"name": _display_name(user), "code": code, "minutes": settings.EMAIL_OTP_MINUTES},
    )


def send_verification_code(user, code: str) -> None:
    send_email_after_commit(
        user.email,
        "Your Choropia verification code",
        "verify_code",
        {"name": _display_name(user), "code": code, "minutes": settings.EMAIL_OTP_MINUTES},
    )


def send_password_reset(user, link: str) -> bool:
    return send_email(
        user.email,
        "Reset your Choropia password",
        "password_reset",
        {"name": _display_name(user), "link": link},
    )


# --- payments and orders --------------------------------------------------------------------


def send_payment_received(payment) -> None:
    """Receipt to the buyer, and a "dispatch it" notice to the seller."""
    order = payment.order
    title = order.listing.title
    common = {"order_id": order.id, "listing_title": title, "amount": naira(payment.amount), "reference": payment.reference}
    send_email_after_commit(
        order.buyer.email,
        f"Payment received for order #{order.id}",
        "payment_received",
        {"name": _display_name(order.buyer), "seller_name": order.seller.get_full_name() or "the seller", **common},
    )
    send_email_after_commit(
        order.seller.email,
        f"You have a paid order: #{order.id}",
        "new_paid_order",
        {"name": _display_name(order.seller), "buyer_name": order.buyer.get_full_name() or "A buyer", **common},
    )


# What each recipient is told about a status change. (paid_escrow is covered by the payment emails.)
_ORDER_COPY = {
    "courier_assigned": ("buyer", "A courier has been assigned", "The seller has handed your order to a courier."),
    "in_transit": ("buyer", "Your order is on its way", "Your courier is on the way with your item."),
    "delivered": ("buyer", "Your order was delivered", "Please check your item. If everything is as described, confirm receipt so the seller can be paid. If something is wrong, open a dispute from the order page."),
    "completed": ("both", "Order completed", "This order is complete. Thank you for using Choropia."),
    "refunded": ("buyer", "Your order was refunded", "Your payment is being returned to you."),
    "disputed": ("both", "A dispute was opened", "A dispute was opened on this order. The payment stays safely in escrow while our team reviews it."),
}


def send_order_update(order, to_status: str, recipient, actor=None) -> None:
    rule = _ORDER_COPY.get(to_status)
    if rule is None:
        return
    audience, headline, body = rule
    role = "buyer" if recipient.id == order.buyer_id else "seller"
    if audience != "both" and audience != role:
        return
    send_email_after_commit(
        recipient.email,
        f"Order #{order.id}: {headline.lower()}",
        "order_update",
        {
            "name": _display_name(recipient),
            "headline": headline,
            "body": body,
            "order_id": order.id,
            "listing_title": order.listing.title,
            "status": to_status.replace("_", " "),
        },
    )


# --- payouts --------------------------------------------------------------------------------


def send_payout_sent(payout) -> None:
    seller = payout.seller
    send_email_after_commit(
        seller.email,
        f"Your payout of {naira(payout.net_amount)} is on its way",
        "payout_sent",
        {
            "name": _display_name(seller),
            "order_id": payout.payment.order_id,
            "gross": naira(payout.gross_amount),
            "commission": naira(payout.commission_amount),
            "rate": f"{payout.commission_rate.normalize():f}",
            "net": naira(payout.net_amount),
            "bank": payout.bank_name,
            "last4": payout.account_last4,
        },
    )


def send_payout_needs_account(payout) -> None:
    seller = payout.seller
    send_email_after_commit(
        seller.email,
        "Add your bank account to receive your money",
        "payout_needs_account",
        {"name": _display_name(seller), "order_id": payout.payment.order_id, "net": naira(payout.net_amount)},
    )
