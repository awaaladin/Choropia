import json
import logging
from decimal import Decimal

from django.conf import settings
from django.db.models import Q, Sum
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import generics, permissions, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from orders.models import Order

from .gaxtron import GaxtronClient, GaxtronError
from .models import Payment
from .naming import is_ours
from .paystack import PaystackClient, PaystackError
from .serializers import WalletTransactionSerializer
from .services import confirm_payment, confirm_paystack_payment, initialize_payment, verify_paystack_payment

logger = logging.getLogger(__name__)


class InitializePaymentView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        order_id = request.data.get("order_id")
        if not order_id:
            raise ValidationError({"order_id": "This field is required."})

        order = Order.objects.filter(id=order_id).first()
        if order is None:
            raise ValidationError({"order_id": "Order not found."})
        if order.buyer_id != request.user.id:
            raise PermissionDenied("Only the buyer can initialize payment for this order.")
        if order.status != Order.Status.PENDING_PAYMENT:
            raise ValidationError("This order is not awaiting payment.")

        try:
            payment = initialize_payment(order, callback_url=request.data.get("callback_url"))
        except (PaystackError, GaxtronError) as exc:
            logger.error("Could not start checkout for order %s: %s", order.id, exc)
            return Response(
                {"detail": "Payment couldn't be started right now. Please try again."},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        return Response(
            {
                "provider": payment.provider,
                "reference": payment.reference,
                "authorization_url": payment.authorization_url,
                "amount": str(payment.amount),
                "crypto_amount": str(payment.crypto_amount) if payment.crypto_amount is not None else None,
                "crypto_currency": payment.crypto_currency,
            }
        )


@method_decorator(csrf_exempt, name="dispatch")
class GaxtronWebhookView(APIView):
    """Gaxtron posts here once a payment's on-chain tx is confirmed. In practice this can only
    fire in production — gaxtron refuses to register a callback_url that resolves to
    localhost/a private IP, so a local/dev Choropia relies entirely on
    payments.tasks.poll_gaxtron_payments_task instead. Kept for when Choropia is deployed
    behind a real public domain."""

    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        signature = request.headers.get("x-gaxtron-signature", "")
        client = GaxtronClient()
        payload = request.data

        if settings.GAXTRON_WEBHOOK_SECRET and not client.verify_webhook_signature(payload, signature):
            return JsonResponse({"detail": "invalid signature"}, status=400)

        if payload.get("status") == "confirmed" and payload.get("payment_id"):
            confirm_payment(payload["payment_id"], tx_hash=payload.get("tx_hash"), raw_payload=payload)

        return JsonResponse({"received": True})


class VerifyPaymentView(APIView):
    """The buyer's app calls this after coming back from Paystack's checkout page, so the order
    moves to escrow straight away instead of waiting for the webhook."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        payment = Payment.objects.select_related("order").filter(
            order_id=request.data.get("order_id"), order__buyer=request.user
        ).first()
        if payment is None:
            raise ValidationError({"order_id": "No payment for this order."})
        try:
            payment = verify_paystack_payment(payment)
        except PaystackError as exc:
            logger.warning("Paystack verify failed for %s: %s", payment.reference, exc)
        payment.order.refresh_from_db(fields=["status"])
        return Response(
            {"reference": payment.reference, "status": payment.status, "order_status": payment.order.status}
        )


@method_decorator(csrf_exempt, name="dispatch")
class PaystackWebhookView(APIView):
    """Paystack events for the shared account arrive through the webhook router, which forwards
    only CHOROPIA- references here, byte for byte, so the HMAC signature still verifies. Token
    auth doesn't apply: the request is authenticated by that signature instead."""

    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        signature = request.headers.get("x-paystack-signature", "")
        if not PaystackClient().verify_webhook_signature(request.body, signature):
            return JsonResponse({"detail": "invalid signature"}, status=400)

        try:
            payload = json.loads(request.body or b"{}")
        except ValueError:
            return JsonResponse({"detail": "invalid JSON"}, status=400)
        data = payload.get("data") or {}
        reference = data.get("reference", "")

        from .payouts import handle_choropia_event

        handle_choropia_event(payload)
        # Anything else (another app's reference, an event we don't act on) is acknowledged so
        # Paystack doesn't keep retrying it.
        return JsonResponse({"received": True})


class WalletSummaryView(APIView):
    """Real numbers only — no "available balance" fiction. Gaxtron has no payout endpoint, so
    "released" here means Choropia has approved the seller to be paid, not that crypto has
    actually left gaxtron's custody (see release_escrow() in services.py)."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user

        def total(**filters):
            return Payment.objects.filter(**filters).aggregate(total=Sum("amount"))["total"] or Decimal("0")

        return Response(
            {
                "currency": "NGN",
                "commission_percent": str(settings.PLATFORM_COMMISSION_PERCENT),
                "selling": {
                    "released_total": str(total(order__seller=user, status=Payment.Status.RELEASED)),
                    "held_total": str(total(order__seller=user, status=Payment.Status.PAID_HELD)),
                },
                "buying": {
                    "held_total": str(total(order__buyer=user, status=Payment.Status.PAID_HELD)),
                    "spent_total": str(
                        total(order__buyer=user, status__in=[Payment.Status.RELEASED, Payment.Status.PAID_HELD])
                    ),
                },
            }
        )


class WalletTransactionsView(generics.ListAPIView):
    serializer_class = WalletTransactionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return (
            Payment.objects.filter(Q(order__buyer=user) | Q(order__seller=user))
            .exclude(status=Payment.Status.INITIALIZED)
            .select_related("order", "order__listing", "order__buyer", "order__seller")
            .order_by("-created_at")
        )
