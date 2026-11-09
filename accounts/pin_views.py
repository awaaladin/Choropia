from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import permissions, serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from . import pin as pin_service


class PinStatusSerializer(serializers.Serializer):
    has_pin = serializers.BooleanField()
    length = serializers.IntegerField()
    locked = serializers.BooleanField()
    locked_until = serializers.DateTimeField(allow_null=True)
    retry_after = serializers.IntegerField(allow_null=True)


class SetPinSerializer(serializers.Serializer):
    pin = serializers.CharField(write_only=True, trim_whitespace=True)
    old_pin = serializers.CharField(write_only=True, required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, required=False, allow_blank=True, trim_whitespace=False)
    email_code = serializers.CharField(write_only=True, required=False, allow_blank=True)


class TransactionPinView(APIView):
    """GET: whether you have a PIN and whether it is locked. POST: set your first PIN, or change it with your current PIN,
    your password, or a code from POST account/pin/reset-code/."""

    permission_classes = [permissions.IsAuthenticated]
    throttle_scope = "pin"

    @extend_schema(responses=PinStatusSerializer)
    def get(self, request):
        return Response(PinStatusSerializer(pin_service.status(request.user)).data)

    @extend_schema(request=SetPinSerializer, responses=PinStatusSerializer)
    def post(self, request):
        body = SetPinSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        try:
            pin_service.set_pin(
                request.user,
                data["pin"],
                old_pin=data.get("old_pin") or None,
                password=data.get("password") or None,
                email_code=data.get("email_code") or None,
            )
        except pin_service.PinError as exc:
            return Response(exc.as_response_data(), status=423 if exc.code == "pin_locked" else 400)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response(PinStatusSerializer(pin_service.status(request.user)).data)


class PinResetCodeView(APIView):
    """Emails a 6-digit code that can be used instead of the old PIN or password to set a new PIN."""

    permission_classes = [permissions.IsAuthenticated]
    throttle_scope = "otp"

    @extend_schema(request=None, responses=inline_serializer("PinResetCode", {"detail": serializers.CharField()}))
    def post(self, request):
        from django.conf import settings

        from notifications import emails

        from . import otp

        try:
            code = otp.issue_code(request.user, purpose=pin_service.RESET_PIN_PURPOSE)
        except otp.OTPCooldown as exc:
            return Response({"detail": str(exc), "retry_after": exc.seconds_left}, status=429)
        emails.send_pin_reset_code(request.user, code)
        return Response({"detail": "We sent a code to your email.", "expires_in_minutes": settings.EMAIL_OTP_MINUTES})
