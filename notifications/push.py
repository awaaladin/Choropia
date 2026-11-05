"""Phone push notifications through Firebase Cloud Messaging (the only way Android wakes a closed app).

Dormant until FIREBASE_SERVICE_ACCOUNT_JSON is set (the Firebase service-account key, as one line of JSON). Until then every
function here quietly does nothing, so the rest of Choropia is unaffected. A push is best-effort and can never fail the
request that caused it; the in-app notification list is still the source of truth.

We talk to FCM's HTTP v1 API directly: sign a short-lived JWT with the service-account key, swap it for an access token
(cached), then POST the message. Messages are data-only, so the app builds every notification itself and a tap always opens
the right screen.
"""
import base64
import json
import logging
import time

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from django.conf import settings
from django.core.cache import cache
from django.db import transaction

from .models import DeviceToken, Notification

logger = logging.getLogger(__name__)

TOKEN_CACHE_KEY = "fcm-access-token"
SCOPE = "https://www.googleapis.com/auth/firebase.messaging"
TITLES = {
    Notification.Type.MESSAGE: "New message",
    Notification.Type.ORDER_STATUS: "Order update",
    Notification.Type.DISPUTE: "Dispute",
    Notification.Type.DISPATCH: "Delivery update",
    Notification.Type.FOLLOW: "New follower",
    Notification.Type.NEW_LISTING: "New listing",
}


def _account():
    raw = getattr(settings, "FIREBASE_SERVICE_ACCOUNT_JSON", "")
    if not raw:
        return None
    try:
        return json.loads(raw)
    except ValueError:
        logger.error("FIREBASE_SERVICE_ACCOUNT_JSON is not valid JSON")
        return None


def is_configured() -> bool:
    return _account() is not None


def _b64(data: bytes) -> bytes:
    return base64.urlsafe_b64encode(data).rstrip(b"=")


def _access_token(account) -> str:
    token = cache.get(TOKEN_CACHE_KEY)
    if token:
        return token
    now = int(time.time())
    header = _b64(json.dumps({"alg": "RS256", "typ": "JWT"}).encode())
    claims = _b64(
        json.dumps(
            {
                "iss": account["client_email"],
                "scope": SCOPE,
                "aud": "https://oauth2.googleapis.com/token",
                "iat": now,
                "exp": now + 3600,
            }
        ).encode()
    )
    signing_input = header + b"." + claims
    key = serialization.load_pem_private_key(account["private_key"].encode(), password=None)
    signature = key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
    assertion = (signing_input + b"." + _b64(signature)).decode()
    response = requests.post(
        "https://oauth2.googleapis.com/token",
        data={"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": assertion},
        timeout=5,
    )
    response.raise_for_status()
    body = response.json()
    cache.set(TOKEN_CACHE_KEY, body["access_token"], max(60, int(body.get("expires_in", 3600)) - 300))
    return body["access_token"]


def _target(notification):
    """Which screen a tap should open: (kind, id) understood by the app and website."""
    ct = notification.target_content_type
    if ct is None or notification.target_object_id is None:
        return "", ""
    model = ct.model
    kinds = {"conversation": "chat", "order": "order", "listing": "listing", "merchant": "merchant"}
    return kinds.get(model, ""), str(notification.target_object_id)


def _send_one(account, access_token, device, title, body, data) -> None:
    url = f"https://fcm.googleapis.com/v1/projects/{account['project_id']}/messages:send"
    response = requests.post(
        url,
        headers={"Authorization": f"Bearer {access_token}"},
        json={"message": {"token": device.token, "data": data, "android": {"priority": "HIGH"}}},
        timeout=5,
    )
    if response.status_code == 404 or (response.status_code == 400 and "UNREGISTERED" in response.text.upper()):
        device.delete()  # the app was uninstalled or the token rotated
    elif not response.ok:
        logger.warning("FCM refused a push (%s): %s", response.status_code, response.text[:200])


def send_to_user(notification: Notification) -> None:
    """Pushes one notification to every phone the recipient has signed in on."""
    try:
        account = _account()
        if account is None:
            return
        devices = list(DeviceToken.objects.filter(user_id=notification.recipient_id))
        if not devices:
            return
        kind, target_id = _target(notification)
        data = {
            "title": TITLES.get(notification.notification_type, "Choropia"),
            "body": notification.verb,
            "type": notification.notification_type,
            "target": kind,
            "target_id": target_id,
            "notification_id": str(notification.pk),
        }
        token = _access_token(account)
        for device in devices:
            _send_one(account, token, device, data["title"], data["body"], data)
    except Exception:  # noqa: BLE001 - a push must never break the request that caused it
        logger.exception("Could not send push for notification %s", notification.pk)


def send_after_commit(notification: Notification) -> None:
    if is_configured():
        transaction.on_commit(lambda: send_to_user(notification))
