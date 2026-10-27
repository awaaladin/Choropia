from django.conf import settings
from django.http import Http404
from django.shortcuts import render
from django.template.loader import render_to_string
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Acceptance
from .services import DOCUMENTS, has_accepted_current, record_acceptance


def _context():
    return {
        "company": getattr(settings, "LEGAL_COMPANY_NAME", "Choropia"),
        "contact_email": getattr(settings, "LEGAL_CONTACT_EMAIL", ""),
        "version": settings.LEGAL_VERSION,
        "commission_note": "6% for items under 10,000 naira, 5% up to 100,000 naira, and 4% above that",
        "driver_commission": f"{settings.DRIVER_COMMISSION_PERCENT.normalize():f}%",
    }


def _body(slug):
    if slug not in DOCUMENTS:
        raise Http404()
    return render_to_string(f"legal/documents/{slug}.html", _context())


def page(request, slug):
    """A plain, readable web page for a legal document (the apps open this in the browser)."""
    return render(request, "legal/page.html", {"title": DOCUMENTS.get(slug) or "", "body": _body(slug), **_context()})


class LegalIndexView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request):
        return Response({
            "version": settings.LEGAL_VERSION,
            "documents": [{"slug": s, "title": t, "url": f"/legal/{s}/"} for s, t in DOCUMENTS.items()],
        })


class LegalDocumentView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request, slug):
        return Response({"slug": slug, "title": DOCUMENTS[slug] if slug in DOCUMENTS else "", "version": settings.LEGAL_VERSION, "html": _body(slug)})


class AcceptanceView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response({
            "version": settings.LEGAL_VERSION,
            "accepted": {s: has_accepted_current(request.user, s) for s in DOCUMENTS},
        })

    def post(self, request):
        documents = [d for d in (request.data.get("documents") or ["terms", "privacy"]) if d in DOCUMENTS]
        record_acceptance(request.user, documents, request)
        return self.get(request)
