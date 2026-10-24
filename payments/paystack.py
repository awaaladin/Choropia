"""
Thin wrapper around the Paystack REST API.

Choropia uses Paystack's standard "charge now, transfer later" pattern to emulate escrow: the
buyer pays the full amount into the platform's own Paystack balance (a normal transaction
charge), and the hold is enforced by Choropia simply not paying the seller until the Order state
machine reaches CONFIRMED/COMPLETED. Paystack has no native "hold" primitive.

The Paystack account is shared with other apps, so every reference Choropia creates starts with
CHOROPIA- (see naming.py) and a webhook router in front of the account forwards Choropia's events
here. The router forwards the body untouched, so the HMAC signature still verifies.
"""
import hashlib
import hmac
from decimal import Decimal

import requests
from django.conf import settings


class PaystackError(Exception):
    def __init__(self, message, http_status=None):
        super().__init__(message)
        self.http_status = http_status  # None when Paystack could not be reached at all


def to_kobo(amount) -> int:
    return int((Decimal(amount) * 100).to_integral_value())


def from_kobo(kobo) -> Decimal:
    return (Decimal(kobo) / 100).quantize(Decimal("0.01"))


class PaystackClient:
    def __init__(self, secret_key=None, base_url=None):
        self.secret_key = secret_key or settings.PAYSTACK_SECRET_KEY
        self.base_url = (base_url or settings.PAYSTACK_BASE_URL).rstrip("/")

    def _request(self, method, path, timeout=15, **kwargs):
        if not self.secret_key:
            raise PaystackError("PAYSTACK_SECRET_KEY is not set")
        try:
            response = requests.request(
                method,
                f"{self.base_url}{path}",
                headers={"Authorization": f"Bearer {self.secret_key}"},
                timeout=timeout,
                **kwargs,
            )
            data = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise PaystackError(f"Paystack unreachable: {exc}") from exc
        if not response.ok or not data.get("status", False):
            raise PaystackError(
                data.get("message", f"Paystack request to {path} failed ({response.status_code})"),
                http_status=response.status_code,
            )
        return data["data"]

    def initialize_transaction(self, email, amount, reference, callback_url, metadata):
        return self._request(
            "POST",
            "/transaction/initialize",
            json={
                "email": email,
                "amount": to_kobo(amount),
                "currency": "NGN",
                "reference": reference,
                "callback_url": callback_url,
                "metadata": metadata,
            },
        )

    def verify_transaction(self, reference):
        return self._request("GET", f"/transaction/verify/{reference}")

    def refund(self, reference):
        return self._request("POST", "/refund", json={"transaction": reference})

    # --- payouts (Paystack Transfers) -------------------------------------------------------

    def list_banks(self, max_pages=6):
        """Every Nigerian bank Paystack can pay out to. Paystack pages the list by cursor."""
        banks, cursor = [], None
        for _ in range(max_pages):
            params = {"country": "nigeria", "currency": "NGN", "perPage": 100, "use_cursor": "true"}
            if cursor:
                params["next"] = cursor
            try:
                response = requests.get(
                    f"{self.base_url}/bank", params=params, headers={"Authorization": f"Bearer {self.secret_key}"}, timeout=15
                )
                body = response.json()
            except (requests.RequestException, ValueError) as exc:
                raise PaystackError(f"Paystack unreachable: {exc}") from exc
            if not response.ok or not body.get("status", False):
                raise PaystackError(body.get("message", "Could not load banks"), http_status=response.status_code)
            banks += [b for b in body.get("data", []) if b.get("active", True)]
            cursor = (body.get("meta") or {}).get("next")
            if not cursor:
                break
        return banks

    def resolve_account(self, account_number, bank_code):
        """Asks the bank who owns this account. Returns {account_number, account_name}."""
        return self._request("GET", "/bank/resolve", params={"account_number": account_number, "bank_code": bank_code})

    def create_recipient(self, name, account_number, bank_code):
        return self._request(
            "POST",
            "/transferrecipient",
            json={"type": "nuban", "name": name, "account_number": account_number, "bank_code": bank_code, "currency": "NGN"},
        )

    def initiate_transfer(self, amount, recipient_code, reference, reason):
        """Pays `amount` NGN out of the Paystack balance. Short timeout: Vercel stops functions at 10 s."""
        return self._request(
            "POST",
            "/transfer",
            timeout=8,
            json={
                "source": "balance",
                "amount": to_kobo(amount),
                "currency": "NGN",
                "recipient": recipient_code,
                "reference": reference,
                "reason": reason,
            },
        )

    def verify_transfer(self, reference):
        return self._request("GET", f"/transfer/verify/{reference}")

    def verify_webhook_signature(self, request_body: bytes, signature_header: str) -> bool:
        if not self.secret_key or not signature_header:
            return False
        computed = hmac.new(self.secret_key.encode("utf-8"), request_body, hashlib.sha512).hexdigest()
        return hmac.compare_digest(computed, signature_header)
