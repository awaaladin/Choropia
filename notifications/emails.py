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


URGENT_TEMPLATES = {"welcome", "verify_code", "password_reset"}  # codes that expire: they may use the whole limit


def _limit() -> int:
    return int(getattr(settings, "EMAIL_DAILY_LIMIT", 400))


def sent_last_24h() -> int:
    from datetime import timedelta

    from .models import EmailSendLog

    return EmailSendLog.objects.filter(sent_at__gte=timezone.now() - timedelta(hours=24)).count()


def _has_room(urgent: bool) -> bool:
    """Everyday emails stop at 85% of the limit so a code someone is waiting for can still go out."""
    cap = _limit() if urgent else int(_limit() * 0.85)
    return sent_last_24h() < cap


def _is_limit_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return any(word in text for word in ("5.4.5", "daily user sending", "sending limit", "quota", "rate limit", "too many"))


def _hold(to, subject, template, context, urgent) -> bool:
    from .models import HeldEmail

    try:
        HeldEmail.objects.create(to=to, subject=" ".join(subject.split())[:300], template=template, context=_jsonable(context or {}), urgent=urgent)
        logger.warning("Email limit reached: held the %s email for %s until there is room", template, _mask(to))
        return True
    except Exception:  # noqa: BLE001
        logger.exception("Could not hold the %s email", template)
        return False


def _jsonable(value):
    import json

    return json.loads(json.dumps(value, default=str))


def _deliver(to, subject, template, context) -> bool:
    """One real send. Raises on failure."""
    from .models import EmailSendLog

    html = render_to_string(f"emails/{template}.html", {**_base_context(), **(context or {})})
    message = EmailMultiAlternatives(
        subject=" ".join(subject.split()),
        body=_plain_text(html),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[to],
    )
    message.attach_alternative(html, "text/html")
    message.send(fail_silently=False)
    EmailSendLog.objects.create()
    logger.info("Sent the %s email to %s", template, _mask(to))
    return True


def send_email(to: str, subject: str, template: str, context: dict | None = None, *, _from_hold: bool = False) -> bool:
    """Renders emails/<template>.html and sends it. Never raises. When the daily sending limit is reached (or the mail
    provider says so) the email is saved and sent later, in order, once there is room: nothing is lost."""
    if not to:
        return False
    urgent = template in URGENT_TEMPLATES
    try:
        if not _from_hold and not _has_room(urgent):
            return _hold(to, subject, template, context, urgent)
        _deliver(to, subject, template, context)
    except Exception as exc:  # noqa: BLE001 - email trouble must never break the caller
        logger.exception("Could not send the %s email to %s", template, _mask(to))
        if not _from_hold and _is_limit_error(exc):
            return _hold(to, subject, template, context, urgent)
        return False
    if not _from_hold:
        flush_held(5)  # a little room may have opened: let a few held emails go
    return True


def held_count() -> int:
    from .models import HeldEmail

    return HeldEmail.objects.filter(sent_at__isnull=True).count()


def flush_held(max_to_send: int = 50) -> int:
    """Sends held emails, oldest first, while there is room under the limit. Returns how many went out."""
    from .models import HeldEmail

    sent = 0
    try:
        for held in HeldEmail.objects.filter(sent_at__isnull=True, attempts__lt=5).order_by("created_at")[:max_to_send]:
            if not _has_room(held.urgent):
                break
            held.attempts += 1
            try:
                _deliver(held.to, held.subject, held.template, held.context)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Could not send held %s email", held.template)
                held.save(update_fields=["attempts"])
                if _is_limit_error(exc):
                    break
                continue
            held.sent_at = timezone.now()
            held.save(update_fields=["attempts", "sent_at"])
            sent += 1
    except Exception:  # noqa: BLE001
        logger.exception("Flushing held emails failed")
    return sent


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


def send_pin_reset_code(user, code: str) -> None:
    send_email_after_commit(
        user.email,
        "Your Choropia PIN reset code",
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
    common = {"order_id": order.id, "order_ref": order.public_id, "listing_title": title, "amount": naira(payment.amount), "reference": payment.reference}
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
    "courier_assigned": ("buyer", "Your order has been dispatched", "The seller has dispatched your order. You will be told when it is on its way."),
    "in_transit": ("buyer", "Your order is on its way", "Your courier is on the way with your item."),
    "delivered": ("buyer", "Your order was delivered", "Please check your item. If everything is as described, confirm receipt so the seller can be paid. If something is wrong, open a dispute from the order page."),
    "completed": ("both", "Order completed", "This order is complete. Thank you for using Choropia."),
    "refunded": ("both", "Order refunded", {"buyer": "Your payment is being returned to you.", "seller": "This order was refunded to the buyer."}),
    "cancelled": ("both", "The order was cancelled", {"buyer": "This order was cancelled. If you paid, your payment is being refunded in full.", "seller": "This order was cancelled before it was paid or dispatched. Nothing more to do."}),
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
    if isinstance(body, dict):
        body = body[role]
    send_email_after_commit(
        recipient.email,
        f"Order #{order.id}: {headline.lower()}",
        "order_update",
        {
            "name": _display_name(recipient),
            "headline": headline,
            "body": body,
            "order_id": order.id,
            "order_ref": order.public_id,
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
            "order_ref": payout.payment.order.public_id,
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
        {"name": _display_name(seller), "order_id": payout.payment.order_id, "order_ref": payout.payment.order.public_id, "net": naira(payout.net_amount)},
    )


# --- dispatch (drivers) ---------------------------------------------------------------------


CONGRATULATIONS = {
    "storefront": {
        "subject": "Congratulations! Your Choropia storefront is approved and verified",
        "eyebrow": "Storefront approved",
        "headline": "{business} is now verified",
        "intro": "We checked your application and we are delighted to welcome {business} to Choropia as a verified storefront. Your shop is ready for buyers.",
        "perks": [
            "The Choropia verified badge next to your name on every listing and on your profile",
            "A lower Choropia fee on your sales (the verified rate)",
            "Your own storefront page that buyers can follow",
            "Buyers see that real people checked your shop, so they trust you faster",
        ],
        "cta": "Post your first listing",
        "link": "/listings/new",
        "closing": "Keep your photos clear and your replies quick. Buyers who get fast answers come back.",
    },
    "driver": {
        "subject": "Congratulations! You are approved as a Choropia driver",
        "eyebrow": "Driver approved",
        "headline": "You are approved to deliver",
        "intro": "Your documents have been checked and you are now an approved Choropia driver. Sellers and buyers can choose you for deliveries.",
        "perks": [
            "Add the areas you serve and set your own prices for each route",
            "Get alerted when a delivery near you is paid for, first to accept gets the job",
            "Get paid for every delivery once the buyer confirms it",
            "Your photo proof and the buyer's handover code keep every delivery safe for you",
        ],
        "cta": "Set up my routes",
        "link": "/driver",
        "closing": "The more areas you cover and the faster you reply, the more jobs you will get.",
    },
    "seller": {
        "subject": "Congratulations! You are a verified Choropia seller",
        "eyebrow": "Verified seller",
        "headline": "You are now a verified seller",
        "intro": "The Choropia team has verified your account, so buyers will see that you are a trusted seller.",
        "perks": [
            "The Choropia verified badge next to your name on every listing and on your profile",
            "A lower Choropia fee on your sales (the verified rate)",
            "More trust from buyers, which means more sales",
        ],
        "cta": "Go to my listings",
        "link": "/my-listings",
        "closing": "Keep delivering great experiences. Honest reviews from buyers will build your reputation even more.",
    },
}


def send_congratulations(user, kind: str, **extra) -> None:
    """A warm, designed "you were approved" email with the Choropia verified badge. kind: storefront, driver or seller.
    Sent after commit; a mail problem never fails the approval."""
    spec = CONGRATULATIONS[kind]
    fill = {"business": extra.get("business") or "Your shop", **extra}
    send_email_after_commit(
        user.email,
        spec["subject"],
        "congratulations",
        {
            "name": _display_name(user),
            "eyebrow": spec["eyebrow"],
            "headline": spec["headline"].format(**fill),
            "intro": spec["intro"].format(**fill),
            "perks": spec["perks"],
            "cta": spec["cta"],
            "link": spec["link"],
            "closing": spec["closing"],
        },
    )


def send_storefront_renamed(user, old_name: str, new_name: str) -> None:
    """Tells the owner their storefront name changed (so a hijacked account cannot rename quietly)."""
    send_email_after_commit(
        user.email,
        f"Your Choropia storefront is now called {new_name}",
        "storefront_renamed",
        {"name": _display_name(user), "old_name": old_name, "new_name": new_name},
    )


def send_dispatch_notice(user, subject: str, headline: str, body: str, link: str = "") -> None:
    """One plain notice about delivery: a job alert, an approval, a reminder. Sent after commit."""
    send_email_after_commit(
        user.email,
        subject,
        "dispatch_notice",
        {"name": _display_name(user), "headline": headline, "body": body, "link": link},
    )
