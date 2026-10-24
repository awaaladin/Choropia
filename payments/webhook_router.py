"""
The one Paystack webhook for the whole shared account.

Paystack allows a single webhook URL per account (per mode), but six products share this account:
Choropia, Mirror, NutriScan, SplitStay, VisionMirror and Voice Verse. Paystack is pointed here
(`/api/paystack-webhook`); this checks Paystack's signature, works out which product an event
belongs to, and either handles it (Choropia's own) or forwards the *exact same body and signature*
to that product's webhook, which verifies the signature again with the same secret key.

This is a port of the standalone `paystack-router` project so Choropia can host it without a
second deployment. It is deliberately a plain Django view (not DRF): the body must reach the other
products byte for byte, and DRF's parsers/throttles have no business in front of a webhook.

Routing rules (unchanged from the original router):
  1. `metadata.app` wins (also when Paystack hands it back as a JSON string);
  2. otherwise the reference prefix: `NUTRISCAN-PROYEAR-...` -> NUTRISCAN. Refunds and disputes
     carry the original transaction's reference instead of their own;
  3. SplitStay's older `CP-` / `cp-po-` references still go to SplitStay.

Where each product's webhook lives is configuration: `ROUTE_<APP>=https://...` environment
variables. A product with no route is simply not forwarded to (the event is acknowledged and
logged as unrouted so Paystack doesn't retry it forever).

Answers Paystack with: 401 bad signature, 200 handled/forwarded/unclaimed, 502 the product was
down or refused it (so Paystack retries later).
"""
import json
import logging
import os

import requests
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from .naming import APP_CODE as CHOROPIA, is_ours
from .paystack import PaystackClient
from .services import confirm_paystack_payment

logger = logging.getLogger(__name__)

# Every product's code, as used at the start of its references and in metadata.app.
APP_CODES = ["CHOROPIA", "MIRROR", "NUTRISCAN", "SPLITSTAY", "VISIONMIRROR", "VOICEVERSE"]

# Prefixes used before the shared naming scheme, still in flight for payments started earlier.
LEGACY_PREFIXES = {"CP": "SPLITSTAY"}

# Vercel's Hobby functions stop at 10 s; forwarding must give up before that so we can answer 502.
FORWARD_TIMEOUT_SECONDS = 8


def _metadata_of(data):
    metadata = (data or {}).get("metadata")
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except ValueError:
            return {}
    return metadata if isinstance(metadata, dict) else {}


def _code_from_reference(reference):
    if not isinstance(reference, str) or "-" not in reference:
        return ""
    prefix = reference.split("-")[0].upper()
    return LEGACY_PREFIXES.get(prefix, prefix)


def app_for(payload):
    """The app code an event is for, or "" when it can't be told."""
    data = (payload or {}).get("data") or {}
    transaction = data.get("transaction") if isinstance(data.get("transaction"), dict) else {}
    candidates = [
        _metadata_of(data).get("app"),
        _metadata_of(transaction).get("app"),
        _code_from_reference(data.get("reference")),
        _code_from_reference(data.get("transaction_reference")),
        _code_from_reference(transaction.get("reference")),
    ]
    for candidate in candidates:
        code = candidate.upper() if isinstance(candidate, str) else ""
        if code in APP_CODES:
            return code
    return ""


def routes_from(environ):
    """Reads ROUTE_<APP>=https://... for the other products. Choropia's own is handled in-process."""
    routes = {}
    for code in APP_CODES:
        url = (environ.get(f"ROUTE_{code}") or "").strip()
        if url and code != CHOROPIA:
            routes[code] = url
    return routes


def _handle_choropia_event(payload):
    data = payload.get("data") or {}
    reference = data.get("reference", "")
    if payload.get("event") == "charge.success" and is_ours(reference):
        confirm_paystack_payment(reference, data, raw_payload=payload)


@method_decorator(csrf_exempt, name="dispatch")
class PaystackRouterView(View):
    http_method_names = ["post"]

    def post(self, request):
        raw = request.body
        signature = request.headers.get("x-paystack-signature", "")
        if not PaystackClient().verify_webhook_signature(raw, signature):
            return JsonResponse({"error": "invalid signature"}, status=401)

        try:
            payload = json.loads(raw.decode("utf-8") or "{}")
        except ValueError:
            return JsonResponse({"error": "invalid JSON"}, status=400)
        if not isinstance(payload, dict):
            return JsonResponse({"error": "invalid JSON"}, status=400)

        app = app_for(payload)
        event = payload.get("event")
        reference = (payload.get("data") or {}).get("reference", "?")

        if app == CHOROPIA:
            try:
                _handle_choropia_event(payload)
            except Exception:  # noqa: BLE001 - any failure must make Paystack retry, not drop the event
                logger.exception("Choropia could not process %s %s", event, reference)
                return JsonResponse({"routed": False, "app": app, "error": "processing failed"}, status=502)
            return JsonResponse({"routed": True, "app": app})

        target = routes_from(os.environ).get(app)
        if not target:
            logger.warning("unrouted %s reference=%s app=%s", event, reference, app or "unknown")
            return JsonResponse({"routed": False, "app": app or None})

        try:
            forwarded = requests.post(
                target,
                data=raw,  # the exact bytes Paystack signed
                headers={"Content-Type": "application/json", "x-paystack-signature": signature},
                timeout=FORWARD_TIMEOUT_SECONDS,
                allow_redirects=False,
            )
        except requests.RequestException as exc:
            logger.error("%s %s -> %s failed: %s", event, reference, app, exc)
            return JsonResponse({"routed": False, "app": app, "error": "upstream unreachable"}, status=502)

        logger.info("%s %s -> %s %s", event, reference, app, forwarded.status_code)
        if forwarded.ok:
            return JsonResponse({"routed": True, "app": app})
        return JsonResponse({"routed": False, "app": app, "upstream": forwarded.status_code}, status=502)
