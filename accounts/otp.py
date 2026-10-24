"""
Email one-time codes (OTP): prove a person controls the email address on their account.

Used for email verification after signup, and available for any sensitive action (the payout
account can be gated on a verified email with REQUIRE_VERIFIED_EMAIL_FOR_PAYOUT).

Design:
* 6-digit code, valid EMAIL_OTP_MINUTES (10), single use, at most EMAIL_OTP_MAX_ATTEMPTS wrong
  guesses per code, and a EMAIL_OTP_RESEND_SECONDS cooldown between codes. Together with the "otp"
  request throttle, guessing a code is not practical.
* Only a keyed hash of the code is stored (HMAC with SECRET_KEY), never the code itself.
* Issuing a new code retires the previous one.
"""
import hashlib
import hmac
import secrets
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from .models import EmailOTP

VERIFY_EMAIL = "verify_email"


class OTPCooldown(Exception):
    def __init__(self, seconds_left: int):
        super().__init__(f"Wait {seconds_left} seconds before asking for another code.")
        self.seconds_left = seconds_left


def _hash(user_id: int, purpose: str, code: str) -> str:
    message = f"{user_id}:{purpose}:{code}".encode()
    return hmac.new(settings.SECRET_KEY.encode(), message, hashlib.sha256).hexdigest()


def issue_code(user, purpose: str = VERIFY_EMAIL) -> str:
    """Creates a new code (retiring any earlier one) and returns it so the caller can email it."""
    now = timezone.now()
    latest = EmailOTP.objects.filter(user=user, purpose=purpose).order_by("-created_at").first()
    if latest is not None:
        wait = timedelta(seconds=settings.EMAIL_OTP_RESEND_SECONDS) - (now - latest.created_at)
        if wait.total_seconds() > 0:
            raise OTPCooldown(int(wait.total_seconds()) + 1)
    EmailOTP.objects.filter(user=user, purpose=purpose, consumed_at__isnull=True).update(consumed_at=now)

    code = f"{secrets.randbelow(10 ** 6):06d}"
    EmailOTP.objects.create(
        user=user,
        purpose=purpose,
        code_hash=_hash(user.pk, purpose, code),
        expires_at=now + timedelta(minutes=settings.EMAIL_OTP_MINUTES),
    )
    return code


def check_code(user, code: str, purpose: str = VERIFY_EMAIL) -> bool:
    """True exactly once for the right, unexpired code. Wrong guesses are counted against it."""
    now = timezone.now()
    otp = (
        EmailOTP.objects.select_for_update()
        .filter(user=user, purpose=purpose, consumed_at__isnull=True, expires_at__gt=now)
        .order_by("-created_at")
        .first()
    )
    if otp is None:
        return False
    otp.attempts += 1
    if otp.attempts > settings.EMAIL_OTP_MAX_ATTEMPTS:
        otp.consumed_at = now
        otp.save(update_fields=["attempts", "consumed_at", "updated_at"])
        return False
    if hmac.compare_digest(otp.code_hash, _hash(user.pk, purpose, str(code))):
        otp.consumed_at = now
        otp.save(update_fields=["attempts", "consumed_at", "updated_at"])
        return True
    otp.save(update_fields=["attempts", "updated_at"])
    return False
