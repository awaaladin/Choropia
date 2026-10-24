import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import generics, permissions, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from .serializers import (
    EmailOrPhoneTokenObtainPairSerializer,
    MeUpdateSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RegisterSerializer,
    UserSerializer,
)

User = get_user_model()
logger = logging.getLogger(__name__)


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]
    throttle_scope = "auth"

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        self._send_welcome(user)
        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "user": UserSerializer(user).data,
                "refresh": str(refresh),
                "access": str(refresh.access_token),
            },
            status=201,
        )


    @staticmethod
    def _send_welcome(user):
        """Welcome email carrying the verification code. Signup must succeed even if email is down."""
        try:
            from notifications import emails

            from . import otp

            emails.send_welcome(user, otp.issue_code(user))
        except Exception:  # noqa: BLE001
            logger.exception("Welcome email could not be prepared for user %s", user.pk)


class LoginView(TokenObtainPairView):
    serializer_class = EmailOrPhoneTokenObtainPairSerializer
    permission_classes = [permissions.AllowAny]
    throttle_scope = "auth"


class LogoutView(APIView):
    """Blacklists the supplied refresh token so it can no longer mint new access tokens."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response({"detail": "refresh token is required"}, status=400)
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except TokenError:
            return Response({"detail": "Invalid or already-blacklisted token"}, status=400)
        return Response(status=204)


class LogoutAllView(APIView):
    """Blacklists every refresh token ever issued to this account, so every signed-in device
    (this one included) needs to log in again. There's no device/session list to revoke
    individually — SimpleJWT's blacklist app tracks issued tokens, not sessions — so this is
    all-or-nothing."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        outstanding = OutstandingToken.objects.filter(user=request.user)
        BlacklistedToken.objects.bulk_create(
            (BlacklistedToken(token=t) for t in outstanding),
            ignore_conflicts=True,
        )
        return Response(status=204)


class PasswordResetRequestView(APIView):
    """Emails a reset link. Always answers 200 whether or not the address is registered, so the
    endpoint can't be used to discover which emails have accounts."""

    permission_classes = [permissions.AllowAny]
    throttle_scope = "auth"

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = User.objects.filter(email__iexact=serializer.validated_data["email"], is_active=True).first()
        if user:
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            link = f"{settings.PASSWORD_RESET_URL_BASE}?uid={uid}&token={token}"
            from notifications import emails

            # Same answer either way so the endpoint can't be used to probe which emails exist;
            # a delivery failure is logged for the operator (check the EMAIL_* settings).
            if not emails.send_password_reset(user, link):
                logger.error("Password reset email could not be sent to user %s", user.pk)
        return Response({"detail": "If that email is registered, a reset link is on its way."})


class PasswordResetConfirmView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_scope = "auth"

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        user.set_password(serializer.validated_data["password"])
        user.save(update_fields=["password"])
        return Response({"detail": "Password updated. You can log in now."})


class MeView(generics.RetrieveUpdateAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user

    def get_serializer_class(self):
        if self.request.method in ("PUT", "PATCH"):
            return MeUpdateSerializer
        return UserSerializer


class UserViewSet(viewsets.ReadOnlyModelViewSet):
    """Public read-only profile lookups (used for storefront/author display, mentions, etc.)."""

    queryset = User.objects.select_related("profile").filter(is_active=True)
    serializer_class = UserSerializer
    search_fields = ("email", "first_name", "last_name")


class EmailOTPRequestView(APIView):
    """Emails the signed-in user a fresh 6-digit code to verify their address."""

    permission_classes = [permissions.IsAuthenticated]
    throttle_scope = "otp"

    def post(self, request):
        from notifications import emails

        from . import otp

        if request.user.profile.email_verified:
            return Response({"email_verified": True, "detail": "Your email is already verified."})
        try:
            code = otp.issue_code(request.user)
        except otp.OTPCooldown as exc:
            return Response({"detail": str(exc), "retry_after": exc.seconds_left}, status=429)
        emails.send_verification_code(request.user, code)
        return Response({"detail": "We sent a code to your email.", "expires_in_minutes": settings.EMAIL_OTP_MINUTES})


class EmailOTPConfirmView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_scope = "otp"

    def post(self, request):
        from django.db import transaction

        from . import otp

        code = str(request.data.get("code", "")).strip()
        if not (code.isdigit() and len(code) == 6):
            return Response({"code": ["Enter the 6-digit code."]}, status=400)
        with transaction.atomic():
            ok = otp.check_code(request.user, code)
            if ok:
                profile = request.user.profile
                profile.email_verified = True
                profile.save(update_fields=["email_verified", "updated_at"])
        if not ok:
            return Response({"detail": "That code is wrong or has expired."}, status=400)
        return Response({"email_verified": True})
