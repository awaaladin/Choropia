"""
Authenticator-app (TOTP, RFC 6238) two-factor authentication.

Implemented with the standard library only (hmac/hashlib/base64) so it adds no dependency.

Flow
  1. POST /auth/2fa/setup/    -> secret + otpauth:// URI (user scans it in their authenticator app)
  2. POST /auth/2fa/confirm/  -> user submits a current code; 2FA turns on, recovery codes returned ONCE
  3. Login (/auth/login/ or /auth/google/) now answers {"two_factor_required": true, "challenge": ...}
     instead of tokens; the client then calls POST /auth/2fa/verify/ with the challenge and a code.
  4. POST /auth/2fa/disable/  -> needs the account password plus a valid code (or recovery code)
"""
import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote

from django.conf import settings
from django.core import signing
from django.utils.crypto import constant_time_compare
from rest_framework import permissions, serializers
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import TOTPDevice, User
from .serializers import UserSerializer

PERIOD = 30
DIGITS = 6
WINDOW = 1  # accept the previous and next 30s step too, to tolerate clock drift
CHALLENGE_SALT = "choropia.2fa.challenge"
CHALLENGE_MAX_AGE = 300  # seconds
RECOVERY_CODE_COUNT = 8


# ---- RFC 6238 ------------------------------------------------------------------------------

def generate_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def _hotp(secret: str, counter: int) -> str:
    padded = secret + "=" * (-len(secret) % 8)
    key = base64.b32decode(padded, casefold=True)
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = (struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF) % (10 ** DIGITS)
    return str(code).zfill(DIGITS)


def current_step(now: float | None = None) -> int:
    return int((now if now is not None else time.time()) // PERIOD)


def totp_code(secret: str, step: int | None = None) -> str:
    return _hotp(secret, step if step is not None else current_step())


def match_step(secret: str, code: str, now: float | None = None) -> int | None:
    """Returns the time step the code belongs to, or None if it doesn't match any allowed step."""
    code = (code or "").strip().replace(" ", "")
    if len(code) != DIGITS or not code.isdigit():
        return None
    step = current_step(now)
    for candidate in range(step - WINDOW, step + WINDOW + 1):
        if constant_time_compare(_hotp(secret, candidate), code):
            return candidate
    return None


def provisioning_uri(user, secret: str) -> str:
    issuer = "Choropia"
    label = quote(f"{issuer}:{user.email}")
    return f"otpauth://totp/{label}?secret={secret}&issuer={quote(issuer)}&period={PERIOD}&digits={DIGITS}"


# ---- recovery codes ------------------------------------------------------------------------

def _hash_recovery(code: str) -> str:
    return hashlib.sha256(code.strip().lower().replace("-", "").encode()).hexdigest()


def new_recovery_codes():
    plain = [f"{secrets.token_hex(2)}-{secrets.token_hex(2)}" for _ in range(RECOVERY_CODE_COUNT)]
    return plain, [_hash_recovery(c) for c in plain]


# ---- shared checks -------------------------------------------------------------------------

def check_second_factor(device: TOTPDevice, code: str) -> bool:
    """True if `code` is a fresh TOTP code or an unused recovery code. Consumes what it matches."""
    step = match_step(device.secret, code)
    if step is not None and step > device.last_used_step:
        device.last_used_step = step
        device.save(update_fields=["last_used_step"])
        return True

    hashed = _hash_recovery(code or "")
    if hashed in (device.recovery_hashes or []):
        device.recovery_hashes = [h for h in device.recovery_hashes if h != hashed]
        device.save(update_fields=["recovery_hashes"])
        return True
    return False


def user_has_two_factor(user) -> bool:
    device = getattr(user, "totp_device", None)
    return bool(device and device.confirmed)


def make_challenge(user) -> str:
    return signing.dumps({"uid": user.pk}, salt=CHALLENGE_SALT)


def issue_tokens(user) -> dict:
    refresh = RefreshToken.for_user(user)
    return {
        "user": UserSerializer(user).data,
        "refresh": str(refresh),
        "access": str(refresh.access_token),
    }


def login_response(user) -> dict:
    """What every login path returns: tokens, or a second-factor challenge when 2FA is on."""
    if user_has_two_factor(user):
        return {"two_factor_required": True, "challenge": make_challenge(user)}
    return issue_tokens(user)


# ---- views ---------------------------------------------------------------------------------

class CodeSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=32)


class TwoFactorStatusView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        device = getattr(request.user, "totp_device", None)
        return Response(
            {
                "enabled": bool(device and device.confirmed),
                "recovery_codes_remaining": len(device.recovery_hashes) if device and device.confirmed else 0,
            }
        )


class TwoFactorSetupView(APIView):
    """Starts enrolment. Safe to call again before confirming — it just issues a fresh secret."""

    permission_classes = [permissions.IsAuthenticated]
    throttle_scope = "auth"

    def post(self, request):
        device = getattr(request.user, "totp_device", None)
        if device and device.confirmed:
            return Response({"detail": "Two-factor authentication is already on."}, status=400)

        secret = generate_secret()
        TOTPDevice.objects.update_or_create(
            user=request.user,
            defaults={"secret": secret, "confirmed": False, "last_used_step": 0, "recovery_hashes": []},
        )
        return Response({"secret": secret, "otpauth_uri": provisioning_uri(request.user, secret)})


class TwoFactorConfirmView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_scope = "auth"

    def post(self, request):
        serializer = CodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        device = getattr(request.user, "totp_device", None)
        if device is None:
            return Response({"detail": "Start setup first."}, status=400)
        if device.confirmed:
            return Response({"detail": "Two-factor authentication is already on."}, status=400)

        step = match_step(device.secret, serializer.validated_data["code"])
        if step is None:
            return Response({"detail": "That code isn't right. Check the code in your authenticator app."}, status=400)

        plain, hashed = new_recovery_codes()
        device.confirmed = True
        device.last_used_step = step
        device.recovery_hashes = hashed
        device.save(update_fields=["confirmed", "last_used_step", "recovery_hashes"])
        # The plaintext recovery codes are shown exactly once.
        return Response({"enabled": True, "recovery_codes": plain})


class TwoFactorDisableView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_scope = "auth"

    def post(self, request):
        device = getattr(request.user, "totp_device", None)
        if not (device and device.confirmed):
            return Response({"detail": "Two-factor authentication isn't on."}, status=400)

        password = request.data.get("password", "")
        code = request.data.get("code", "")
        if not request.user.check_password(password):
            return Response({"detail": "Incorrect password."}, status=400)
        if not check_second_factor(device, code):
            return Response({"detail": "That code isn't right."}, status=400)

        device.delete()
        return Response({"enabled": False})


class TwoFactorVerifyView(APIView):
    """Second step of login: exchange a challenge + authenticator code for real tokens."""

    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    throttle_scope = "auth"

    def post(self, request):
        challenge = request.data.get("challenge", "")
        code = request.data.get("code", "")
        try:
            payload = signing.loads(challenge, salt=CHALLENGE_SALT, max_age=CHALLENGE_MAX_AGE)
        except signing.BadSignature:
            return Response({"detail": "This sign-in has expired. Please log in again."}, status=400)

        user = User.objects.filter(pk=payload.get("uid"), is_active=True).first()
        device = getattr(user, "totp_device", None) if user else None
        if not (device and device.confirmed):
            return Response({"detail": "This sign-in has expired. Please log in again."}, status=400)
        if not check_second_factor(device, code):
            return Response({"detail": "That code isn't right."}, status=400)

        return Response(issue_tokens(user))
