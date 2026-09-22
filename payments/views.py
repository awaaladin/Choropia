from django.conf import settings
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import permissions
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from orders.models import Order

from .gaxtron import GaxtronClient
from .services import confirm_payment, initialize_payment


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

        payment = initialize_payment(order, callback_url=request.data.get("callback_url"))
        return Response(
            {
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
