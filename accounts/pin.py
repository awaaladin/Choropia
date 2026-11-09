"""
Transaction PIN: approves money actions such as creating an escrow offer in chat.

Rules
* TRANSACTION_PIN_LENGTH digits (4). Obvious PINs (0000, 1234, 4321, ...) are refused.
* Stored only as a Django password-hasher hash. The raw PIN is never saved, logged or echoed back.
* Checked with the hasher's constant-time compare. A person with no PIN gets exactly the same answer
  as a wrong PIN, after the same amount of hashing work, so a caller can't tell the two apart.
* PIN_MAX_ATTEMPTS (5) wrong PINs lock it for PIN_LOCK_MINUTES (15). While locked even the right PIN
  is refused. The row is locked (select_for_update) so parallel guesses can't slip past the count.
* Changing a PIN needs the old PIN, the account password, or a code emailed to the person (for people
  who sign in with Google and have no password). The password and email paths also clear a lock:
  they are the "forgot my PIN" route.

verify_pin() commits its own attempt counting. Call it OUTSIDE any surrounding transaction that may roll
back, or a wrong guess could be un-counted.
"""
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.db import transaction
from django.utils import timezone

from .models import TransactionPin

RESET_PIN_PURPOSE = "reset_pin"
GENERIC_MESSAGE = "That PIN is not right."

_dummy_hash = None


def _dummy():
    global _dummy_hash
    if _dummy_hash is None:
        _dummy_hash = make_password("not-a-real-pin")
    return _dummy_hash


class PinError(Exception):
    """code is "pin_invalid" (wrong PIN or no PIN: deliberately the same) or "pin_locked"."""

    def __init__(self, code, message, retry_after=None, attempts_left=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.retry_after = retry_after  # seconds, for pin_locked
        self.attempts_left = attempts_left

    def as_response_data(self):
        data = {"code": self.code, "detail": self.message}
        if self.retry_after is not None:
            data["retry_after"] = self.retry_after
        if self.attempts_left is not None:
            data["attempts_left"] = self.attempts_left
        return data


def pin_length():
    return int(getattr(settings, "TRANSACTION_PIN_LENGTH", 4))


def validate_new_pin(pin) -> str:
    """Returns the PIN as a string, or raises ValueError with a message a person can act on."""
    pin = str(pin or "")
    n = pin_length()
    if len(pin) != n or not pin.isdigit():
        raise ValueError(f"Your PIN must be exactly {n} digits.")
    digits = [int(c) for c in pin]
    steps = {b - a for a, b in zip(digits, digits[1:])}
    if len(set(digits)) == 1 or steps in ({1}, {-1}):
        raise ValueError("That PIN is too easy to guess. Avoid repeated or consecutive digits.")
    return pin


def _locked_seconds(row, now):
    if row is not None and row.locked_until and row.locked_until > now:
        return int((row.locked_until - now).total_seconds()) + 1
    return 0


def status(user) -> dict:
    row = TransactionPin.objects.filter(user=user).first()
    now = timezone.now()
    seconds = _locked_seconds(row, now)
    return {
        "has_pin": row is not None,
        "length": pin_length(),
        "locked": bool(seconds),
        "locked_until": row.locked_until if seconds else None,
        "retry_after": seconds or None,
    }


def verify_pin(user, pin) -> None:
    """Returns None if right; raises PinError otherwise. Attempt counting is committed even when it raises."""
    error = None
    with transaction.atomic():
        row = TransactionPin.objects.select_for_update().filter(user=user).first()
        now = timezone.now()
        locked = _locked_seconds(row, now)
        if locked:
            error = PinError("pin_locked", "Too many wrong PINs. Try again later.", retry_after=locked)
        elif row is None:
            check_password(str(pin or ""), _dummy())  # same work as a real check
            error = PinError("pin_invalid", GENERIC_MESSAGE)
        elif check_password(str(pin or ""), row.pin_hash):
            if row.failed_attempts or row.locked_until:
                row.failed_attempts = 0
                row.locked_until = None
                row.save(update_fields=["failed_attempts", "locked_until", "updated_at"])
        else:
            row.failed_attempts += 1
            max_attempts = settings.PIN_MAX_ATTEMPTS
            if row.failed_attempts >= max_attempts:
                row.failed_attempts = 0
                row.locked_until = now + timedelta(minutes=settings.PIN_LOCK_MINUTES)
                error = PinError(
                    "pin_locked", "Too many wrong PINs. Try again later.",
                    retry_after=settings.PIN_LOCK_MINUTES * 60,
                )
            else:
                error = PinError("pin_invalid", GENERIC_MESSAGE, attempts_left=max_attempts - row.failed_attempts)
            row.save(update_fields=["failed_attempts", "locked_until", "updated_at"])
    if error is not None:
        _audit(user, "pin.locked" if error.code == "pin_locked" else "pin.failed")
        raise error


def set_pin(user, new_pin, *, old_pin=None, password=None, email_code=None) -> None:
    """Sets the first PIN, or changes it with proof: the old PIN, the account password, or an emailed code.
    Raises ValueError (bad new PIN / missing proof / wrong password or code) or PinError (wrong old PIN)."""
    new_pin = validate_new_pin(new_pin)
    existing = TransactionPin.objects.filter(user=user).exists()

    if existing:
        if password:
            if not (user.has_usable_password() and user.check_password(str(password))):
                raise ValueError("Your password is not right.")
        elif email_code:
            from . import otp

            with transaction.atomic():
                ok = otp.check_code(user, str(email_code).strip(), purpose=RESET_PIN_PURPOSE)
            if not ok:
                raise ValueError("That code is wrong or has expired.")
        elif old_pin:
            verify_pin(user, old_pin)  # raises PinError, counted against the lock
        else:
            raise ValueError("Enter your current PIN or your password to change it.")

    with transaction.atomic():
        TransactionPin.objects.update_or_create(
            user=user,
            defaults={"pin_hash": make_password(new_pin), "failed_attempts": 0, "locked_until": None},
        )
    _audit(user, "pin.changed" if existing else "pin.set")


def _audit(user, action):
    import logging

    # Never the PIN; only who and what happened.
    logging.getLogger("choropia.audit").info("%s user=%s", action, user.pk)
