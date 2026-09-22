import json

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework import permissions
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from orders.models import Order

from .paystack import PaystackClient
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
            }
        )


@method_decorator(csrf_exempt, name="dispatch")
class PaystackWebhookView(APIView):
    """Paystack posts events here (e.g. charge.success). Token auth doesn't apply to webhooks —
    the request is authenticated by verifying the Paystack HMAC signature header instead."""

    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        signature = request.headers.get("x-paystack-signature", "")
        client = PaystackClient()

        if settings.PAYSTACK_SECRET_KEY and not client.verify_webhook_signature(request.body, signature):
            return JsonResponse({"detail": "invalid signature"}, status=400)

        payload = json.loads(request.body or "{}")
        event = payload.get("event")

        if event == "charge.success":
            reference = payload.get("data", {}).get("reference")
            if reference:
                confirm_payment(reference, raw_payload=payload)

        return JsonResponse({"received": True})
