"""Receives a page view from the website. Anonymous, cheap, and never able to break a page."""
import re
from urllib.parse import urlparse

from django.conf import settings
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import PageView

BOT = re.compile(r"bot|crawl|spider|slurp|preview|facebookexternalhit|headless|lighthouse|pingdom|uptime|curl|python|wget", re.I)
VISITOR = re.compile(r"^[A-Za-z0-9_-]{8,40}$")


def _device(width):
    try:
        width = int(width)
    except (TypeError, ValueError):
        return ""
    return "phone" if width < 640 else "tablet" if width < 1024 else "desktop"


def _referrer_host(value):
    host = urlparse(str(value or "")).netloc.lower().removeprefix("www.")
    own = urlparse(settings.CHOROPIA_SITE_URL).netloc.lower().removeprefix("www.")
    return "" if not host or host == own or host.endswith("choropia.vercel.app") else host[:120]


class CollectView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    throttle_scope = "analytics"

    def post(self, request):
        data = request.data if hasattr(request.data, "get") else {}
        path = str(data.get("path") or "")[:200]
        visitor = str(data.get("vid") or "")
        agent = request.META.get("HTTP_USER_AGENT", "")
        if not path.startswith("/") or path.startswith("/staff") or not VISITOR.match(visitor) or BOT.search(agent):
            return Response(status=204)
        try:
            PageView.objects.create(
                path=path.split("?")[0].split("#")[0],
                visitor=visitor,
                referrer=_referrer_host(data.get("ref")),
                device=_device(data.get("w")),
                country=(request.META.get("HTTP_X_VERCEL_IP_COUNTRY", "") or "")[:2].upper(),
            )
        except Exception:  # noqa: BLE001 - counting must never fail a page
            pass
        return Response(status=204)
