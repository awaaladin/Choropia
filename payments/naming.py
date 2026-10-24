"""How Choropia labels its money on the shared Paystack account.

One Paystack account serves several apps, so every reference starts with the app code and
every transaction carries the same metadata keys. That lets the dashboard, exports and the
webhook router tell Choropia's payments apart from the other apps':

    CHOROPIA-ORDER-20261023-4F9A2C7B1E0D   buyer paying an order into escrow
"""
import uuid

from django.utils import timezone

APP_CODE = "CHOROPIA"
APP_NAME = "Choropia"


def make_reference(purpose: str, *, length: int = 12) -> str:
    stamp = timezone.now().strftime("%Y%m%d")
    return f"{APP_CODE}-{purpose.upper()}-{stamp}-{uuid.uuid4().hex[:length].upper()}"


def make_transfer_reference(*, length: int = 12) -> str:
    """Reference for a payout to a seller. Paystack requires transfer references to be lowercase
    (16-50 chars of a-z, 0-9, dash, underscore), so unlike charges this one is lowercase:

        choropia-payout-20261024-4f9a2c7b1e0d
    """
    stamp = timezone.now().strftime("%Y%m%d")
    return f"{APP_CODE.lower()}-payout-{stamp}-{uuid.uuid4().hex[:length]}"


def is_ours(reference: str) -> bool:
    return (reference or "").upper().startswith(f"{APP_CODE}-")


def paystack_metadata(purpose: str, description: str, **extra) -> dict:
    """Metadata sent with every transaction. custom_fields show on the Paystack dashboard."""
    return {
        "app": APP_CODE,
        "app_name": APP_NAME,
        "purpose": purpose.upper(),
        **extra,
        "custom_fields": [
            {"display_name": "App", "variable_name": "app", "value": APP_NAME},
            {"display_name": "Payment for", "variable_name": "purpose", "value": description[:200]},
        ],
    }
