"""
Thin wrapper around the Gaxtron crypto payment API — Choropia's escrow payment provider,
replacing Paystack.

Choropia lists prices in NGN but gaxtron settles in ETH only (Sepolia testnet, as of this
integration), so amounts are converted through gaxtron's own /markets/prices endpoint at
checkout time using an approximate NGN/USD rate (settings.GAXTRON_NGN_PER_USD) — there is no
live forex feed wired in.

Escrow "hold" works the same way it did under Paystack: gaxtron just collects the payment into
a wallet it custodies per-payment. There is no gaxtron payout/transfer endpoint, so releasing
escrow to the seller is — same as it was under Paystack — recorded as a status change without a
live transfer; see release_escrow() in services.py.

Gaxtron's own SSRF guard rejects webhook callback URLs that resolve to localhost/private IPs,
so a locally-hosted Choropia can never actually receive its webhook. payments/tasks.py's
poll_gaxtron_payments_task polls gaxtron directly instead (via get_payment_status, which needs
no auth and has no such restriction) and is what dev — and the webhook's retry/failure path in
production — actually relies on.
"""
import hashlib
import hmac
import json
from decimal import Decimal

import requests
from django.conf import settings


class GaxtronError(Exception):
    pass


class GaxtronClient:
    def __init__(self, api_key=None, base_url=None):
        self.api_key = api_key or settings.GAXTRON_API_KEY
        self.base_url = (base_url or settings.GAXTRON_BASE_URL).rstrip("/")

    def _request(self, method, path, auth=True, **kwargs):
        headers = {"Content-Type": "application/json"}
        if auth:
            headers["X-API-Key"] = self.api_key

        response = requests.request(method, f"{self.base_url}{path}", headers=headers, timeout=15, **kwargs)
        try:
            data = response.json()
        except ValueError:
            data = {}
        if not response.ok:
            raise GaxtronError(data.get("detail", f"Gaxtron request to {path} failed ({response.status_code})"))
        return data

    def eth_usd_price(self) -> Decimal:
        data = self._request("GET", "/markets/prices", auth=False)
        return Decimal(str(data["ethereum"]["usd"]))

    def ngn_to_eth(self, ngn_amount) -> Decimal:
        usd = Decimal(ngn_amount) / settings.GAXTRON_NGN_PER_USD
        eth = usd / self.eth_usd_price()
        return eth.quantize(Decimal("0.000000000000000001"))

    def create_payment(self, eth_amount, callback_url, idempotency_key=None):
        payload = {"amount": str(eth_amount), "callback_url": callback_url}
        if idempotency_key:
            payload["idempotency_key"] = idempotency_key
        return self._request("POST", "/create-payment", json=payload)

    def get_payment_status(self, payment_ref):
        return self._request("GET", f"/payment/{payment_ref}", auth=False)

    def verify_webhook_signature(self, payload: dict, signature_header: str) -> bool:
        body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        computed = hmac.new(settings.GAXTRON_WEBHOOK_SECRET.encode("utf-8"), body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(computed, signature_header or "")
