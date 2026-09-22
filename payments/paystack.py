"""
Thin wrapper around the Paystack REST API.

Choropia uses Paystack's standard "charge now, transfer later" pattern to
emulate escrow: the buyer pays the full amount into the platform's own
Paystack balance (a normal transaction charge), and once the order is
confirmed/completed the platform initiates a separate Transfer to the
seller. There is no native Paystack "hold" primitive — the hold is enforced
by Choropia simply not initiating the transfer until the Order state
machine reaches CONFIRMED/COMPLETED.
"""
import hashlib
import hmac

import requests
from django.conf import settings


class PaystackError(Exception):
    pass


class PaystackClient:
    def __init__(self, secret_key=None, base_url=None):
        self.secret_key = secret_key or settings.PAYSTACK_SECRET_KEY
        self.base_url = base_url or settings.PAYSTACK_BASE_URL

    @property
    def _headers(self):
        return {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json",
        }

    def _request(self, method, path, **kwargs):
        response = requests.request(method, f"{self.base_url}{path}", headers=self._headers, timeout=15, **kwargs)
        data = response.json()
        if not response.ok or not data.get("status", False):
            raise PaystackError(data.get("message", "Paystack request failed"))
        return data["data"]

    def initialize_transaction(self, email, amount_kobo, reference, callback_url=None):
        payload = {"email": email, "amount": amount_kobo, "reference": reference}
        if callback_url:
            payload["callback_url"] = callback_url
        return self._request("POST", "/transaction/initialize", json=payload)

    def verify_transaction(self, reference):
        return self._request("GET", f"/transaction/verify/{reference}")

    def create_transfer_recipient(self, name, account_number, bank_code):
        payload = {
            "type": "nuban",
            "name": name,
            "account_number": account_number,
            "bank_code": bank_code,
            "currency": "NGN",
        }
        return self._request("POST", "/transferrecipient", json=payload)

    def initiate_transfer(self, amount_kobo, recipient_code, reason=""):
        payload = {
            "source": "balance",
            "amount": amount_kobo,
            "recipient": recipient_code,
            "reason": reason,
        }
        return self._request("POST", "/transfer", json=payload)

    def refund(self, transaction_reference, amount_kobo=None):
        payload = {"transaction": transaction_reference}
        if amount_kobo is not None:
            payload["amount"] = amount_kobo
        return self._request("POST", "/refund", json=payload)

    def verify_webhook_signature(self, request_body: bytes, signature_header: str) -> bool:
        computed = hmac.new(
            self.secret_key.encode("utf-8"), request_body, hashlib.sha512
        ).hexdigest()
        return hmac.compare_digest(computed, signature_header or "")
