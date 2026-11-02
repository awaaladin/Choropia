"""Where Paystack sends a buyer who paid from the Android app.

The phone's browser is not signed in to Choropia, so showing the website's order page there ends in "token not valid". This page
shows nothing private: it confirms the payment with Paystack, says whether it arrived, and hands the person back to the app
with a button (and an automatic try) that opens choropia://order/<id>."""
import logging
from urllib.parse import quote

from django.conf import settings
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from .models import Payment
from .paystack import PaystackError
from .services import verify_paystack_payment

logger = logging.getLogger(__name__)


@never_cache
@require_GET
def payment_return(request, order_id):
    payment = Payment.objects.filter(order_id=order_id).first()
    reference = request.GET.get("reference") or request.GET.get("trxref") or ""
    # Ask Paystack right away, so the order is already "paid" when the app opens (the webhook can lag behind).
    if payment is not None and payment.status == Payment.Status.INITIALIZED and reference == payment.reference:
        try:
            payment = verify_paystack_payment(payment)
        except PaystackError as exc:
            logger.warning("Return page could not verify order %s: %s", order_id, exc)

    paid = payment is not None and payment.status in (Payment.Status.PAID_HELD, Payment.Status.RELEASED)
    site = settings.CHOROPIA_SITE_URL.rstrip("/")
    web_url = f"{site}/orders/{order_id}"
    app_url = f"choropia://order/{order_id}"
    intent_url = (
        f"intent://order/{order_id}#Intent;scheme=choropia;package=com.choropia.app;"
        f"S.browser_fallback_url={quote(web_url, safe='')};end"
    )
    response = render(request, "payments/return.html", {
        "paid": paid, "app_url": app_url, "intent_url": intent_url, "web_url": web_url, "order_id": order_id,
    })
    response["Referrer-Policy"] = "no-referrer"
    return response
