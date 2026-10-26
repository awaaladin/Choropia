"""API for sellers' payout accounts and payout history, plus the scheduled-jobs endpoint."""
import hmac
import logging
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from rest_framework import generics, permissions, serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from . import payouts
from .models import Payout, PayoutAccount
from .paystack import PaystackError

logger = logging.getLogger(__name__)


class PayoutAccountSerializer(serializers.ModelSerializer):
    """Never includes the full account number or Paystack's recipient code."""

    class Meta:
        model = PayoutAccount
        fields = ("bank_code", "bank_name", "account_last4", "account_name")


class PayoutAccountInputSerializer(serializers.Serializer):
    bank_code = serializers.CharField(max_length=20)
    account_number = serializers.RegexField(r"^\d{10}$", error_messages={"invalid": "Enter the 10-digit account number."})


class PayoutSerializer(serializers.ModelSerializer):
    order_id = serializers.IntegerField(source="payment.order_id", read_only=True)
    listing_title = serializers.CharField(source="payment.order.listing.title", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Payout
        fields = (
            "id", "order_id", "listing_title", "gross_amount", "commission_rate", "commission_amount",
            "net_amount", "status", "status_label", "bank_name", "account_last4", "account_name",
            "created_at", "completed_at",
        )


class BanksView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        try:
            return Response(payouts.nigerian_banks())
        except PaystackError as exc:
            logger.error("Bank list unavailable: %s", exc)
            return Response({"detail": "Banks can't be loaded right now. Please try again."}, status=503)


class PayoutAccountView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_scope = "payout-account"

    def get(self, request):
        account = PayoutAccount.objects.filter(user=request.user).first()
        if account is None:
            return Response({"configured": False})
        return Response({"configured": True, **PayoutAccountSerializer(account).data})

    def put(self, request):
        if settings.REQUIRE_VERIFIED_EMAIL_FOR_PAYOUT and not request.user.profile.email_verified:
            return Response(
                {"detail": "Verify your email address before adding a payout account.", "code": "email_not_verified"},
                status=status.HTTP_403_FORBIDDEN,
            )
        data = PayoutAccountInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            account = payouts.save_payout_account(request.user, data.validated_data["bank_code"], data.validated_data["account_number"])
        except PaystackError as exc:
            logger.info("Payout account rejected for user %s: %s", request.user.id, exc)
            message = "We couldn't verify that account with that bank. Check the bank and the account number."
            if exc.http_status is None or exc.http_status >= 500:
                message = "We couldn't reach the bank right now. Please try again in a moment."
            return Response({"detail": message}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"configured": True, **PayoutAccountSerializer(account).data})

    def delete(self, request):
        PayoutAccount.objects.filter(user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CommissionPreviewView(APIView):
    """Public and read-only: what the seller would pay and receive for a price. The apps call it while a
    seller types the price, so the rate lives in one place (the server)."""

    permission_classes = [permissions.AllowAny]
    authentication_classes: list = []
    throttle_classes: list = []

    def get(self, request):
        try:
            price = Decimal(str(request.query_params.get("price", "")).replace(",", "").strip())
        except (InvalidOperation, ValueError):
            return Response({"price": ["Enter a price in naira."]}, status=status.HTTP_400_BAD_REQUEST)
        if not (Decimal("0") < price <= Decimal("1000000000")):
            return Response({"price": ["Enter a price between 1 and 1,000,000,000."]}, status=status.HTTP_400_BAD_REQUEST)
        preview = payouts.commission_preview(price)
        return Response({key: str(value) for key, value in preview.items()})


class MyPayoutsView(generics.ListAPIView):
    serializer_class = PayoutSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return (
            Payout.objects.filter(seller=self.request.user)
            .select_related("payment__order__listing")
            .order_by("-created_at")
        )


@method_decorator(csrf_exempt, name="dispatch")
class RunScheduledJobsView(View):
    """One endpoint any scheduler can call (Vercel Cron, GitHub Actions, cron on the Docker host).
    Runs the jobs that Celery beat would: confirm waiting payments, auto-release escrow, and send or
    reconcile payouts. Protected by CRON_SECRET (Vercel Cron sends it as a Bearer token)."""

    http_method_names = ["get", "post"]

    def dispatch(self, request, *args, **kwargs):
        secret = settings.CRON_SECRET
        if not secret:
            return JsonResponse({"detail": "Scheduled jobs are not configured."}, status=503)
        token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        if not hmac.compare_digest(token.encode(), secret.encode()):
            return JsonResponse({"detail": "Unauthorized."}, status=401)
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        return self.run()

    def post(self, request):
        return self.run()

    def run(self):
        from .services import retry_pending_refunds
        from .tasks import auto_refund_undispatched_task, auto_release_escrow_task, poll_paystack_payments_task

        results = {}
        for name, job in (
            ("paystack_payments", poll_paystack_payments_task),
            ("auto_release", auto_release_escrow_task),
            ("auto_refund_undispatched", auto_refund_undispatched_task),
            ("pending_refunds", retry_pending_refunds),
            ("payouts", payouts.process_pending_payouts),
        ):
            try:
                results[name] = job()
            except Exception:  # noqa: BLE001 - one failing job must not stop the others
                logger.exception("Scheduled job %s failed", name)
                results[name] = "failed"
        return JsonResponse(results)
