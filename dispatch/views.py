"""Dispatch API (mounted under /api/v1/dispatch/)."""
import re
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from listings.models import Listing
from orders.models import Order

from . import crypto, payloads, services
from .models import (
    Area,
    DeliveryOffer,
    DriverDocument,
    DriverProfile,
    DriverRoute,
    OrderDelivery,
)
from .services import DispatchError

PHONE_RE = re.compile(r"^\+?\d{10,15}$")
MIN_ROUTE_PRICE, MAX_ROUTE_PRICE = Decimal("100"), Decimal("200000")


def _error(exc: DispatchError):
    return Response({"detail": exc.message, "code": exc.code}, status=exc.status)


class DispatchView(APIView):
    """Turns a DispatchError raised anywhere below into a clean 4xx instead of a 500."""

    permission_classes = [permissions.IsAuthenticated]

    def handle_exception(self, exc):
        if isinstance(exc, DispatchError):
            return _error(exc)
        return super().handle_exception(exc)


def _phone(value, label):
    cleaned = re.sub(r"[\s\-()]", "", value or "")
    if not PHONE_RE.match(cleaned):
        raise DispatchError(f"Enter a valid {label} (digits only, for example 08012345678).")
    return cleaned


def _sniff(data: bytes):
    """The real type of an upload from its first bytes (never trust the filename or the declared type)."""
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:5] == b"%PDF-":
        return "application/pdf"
    return None


# --- areas -----------------------------------------------------------------------------------------


class AreasView(DispatchView):
    throttle_scope = "dispatch-write"

    def get_permissions(self):
        return [permissions.AllowAny()] if self.request.method == "GET" else super().get_permissions()

    def get_throttles(self):
        return [] if self.request.method == "GET" else super().get_throttles()

    def get(self, request):
        return Response([{"id": a.id, "name": a.name} for a in Area.objects.filter(is_active=True)])

    def post(self, request):
        area, created = services.add_area(request.data.get("name"), request.user)
        return Response({"id": area.id, "name": area.name}, status=201 if created else 200)


# --- the driver's own side -----------------------------------------------------------------------------


class DriverMeView(DispatchView):
    throttle_scope = "dispatch-write"

    def get(self, request):
        profile = getattr(request.user, "driver_profile", None)
        if profile is None:
            return JsonResponse(None, safe=False)  # a literal JSON null, which apps can parse (an empty body cannot be)
        return Response(payloads.driver_me(profile))

    @transaction.atomic
    def put(self, request):
        """Apply to become a driver, or update the application. Individuals only for now."""
        data = request.data
        profile = getattr(request.user, "driver_profile", None)

        if profile is not None and profile.status in (DriverProfile.Status.APPROVED, DriverProfile.Status.SUSPENDED):
            # Identity details are fixed once approved; they can change how they are reached and go offline.
            if "phone" in data:
                profile.phone = _phone(data["phone"], "phone number")
            if "whatsapp" in data:
                profile.whatsapp = _phone(data["whatsapp"], "WhatsApp number")
            if "available" in data:
                profile.available = bool(data["available"])
            profile.save()
            return Response(payloads.driver_me(profile))

        full_name = " ".join((data.get("full_name") or "").split())
        if len(full_name) < 3:
            raise DispatchError("Enter your full name as it appears on your ID.")
        if data.get("vehicle_type") not in DriverProfile.Vehicle.values:
            raise DispatchError("Choose your vehicle type.")
        guarantor_name = " ".join((data.get("guarantor_name") or "").split())
        if len(guarantor_name) < 3:
            raise DispatchError("Enter your guarantor's full name.")
        if str(data.get("accept_terms")).lower() not in ("true", "1"):
            raise DispatchError("You must accept the Driver Terms and the Privacy Policy to apply.", code="terms_required")

        fields = {
            "full_name": full_name,
            "phone": _phone(data.get("phone"), "phone number"),
            "whatsapp": _phone(data.get("whatsapp"), "WhatsApp number"),
            "vehicle_type": data["vehicle_type"],
            "plate_number": (data.get("plate_number") or "").strip().upper()[:20],
            "guarantor_name": guarantor_name,
            "guarantor_phone": _phone(data.get("guarantor_phone"), "guarantor's phone number"),
        }
        from django.conf import settings

        fields["terms_accepted_version"] = settings.LEGAL_VERSION
        if profile is None:
            profile = DriverProfile.objects.create(user=request.user, **fields)
        else:
            for key, value in fields.items():
                setattr(profile, key, value)
            profile.status = DriverProfile.Status.PENDING  # a rejected driver who corrects things is reviewed again
            profile.review_note = ""
            profile.save()
        from legal.services import record_acceptance

        record_acceptance(request.user, ("driver_terms", "privacy"), request)
        return Response(payloads.driver_me(profile), status=200)


class DriverDocumentsView(DispatchView):
    """Identity documents. They are encrypted before storage and can never be downloaded through this API,
    not even by the driver who uploaded them: only staff reviewing the application can open them."""

    parser_classes = [MultiPartParser, FormParser]
    throttle_scope = "dispatch-documents"

    def get(self, request):
        profile = get_object_or_404(DriverProfile, user=request.user)
        return Response(payloads.driver_me(profile)["documents"])

    @transaction.atomic
    def post(self, request):
        from django.conf import settings

        profile = get_object_or_404(DriverProfile, user=request.user)
        if profile.status == DriverProfile.Status.SUSPENDED:
            raise DispatchError("Your account is suspended.", status=403)
        kind = request.data.get("kind")
        if kind not in DriverDocument.Kind.values:
            raise DispatchError("Choose which document this is.")
        upload = request.FILES.get("file")
        if upload is None:
            raise DispatchError("Attach the document photo or PDF.")
        if upload.size > settings.DOCUMENT_MAX_BYTES:
            raise DispatchError(f"That file is too large (limit {settings.DOCUMENT_MAX_BYTES // (1024 * 1024)} MB).")
        content = upload.read()
        real_type = _sniff(content)
        if real_type is None or (kind == DriverDocument.Kind.PASSPORT_PHOTO and real_type == "application/pdf"):
            raise DispatchError("Upload a clear JPG or PNG photo (PDF is accepted for documents other than the passport photograph).")
        if not crypto.keys_configured():
            raise DispatchError("Document uploads are temporarily unavailable.", code="unavailable", status=503)

        DriverDocument.objects.update_or_create(
            driver=profile,
            kind=kind,
            defaults={"content_type": real_type, "size_bytes": len(content), "encrypted_data": crypto.encrypt(content)},
        )
        if profile.status == DriverProfile.Status.APPROVED:
            # Changing an ID after approval means staff must look again.
            profile.status = DriverProfile.Status.PENDING
            profile.save(update_fields=["status", "updated_at"])
        return Response(payloads.driver_me(profile), status=201)


class DriverRoutesView(DispatchView):
    throttle_scope = "dispatch-write"

    def get(self, request):
        profile = get_object_or_404(DriverProfile, user=request.user)
        routes = profile.routes.select_related("from_area", "to_area")
        return Response([{"id": r.id, "from_area": {"id": r.from_area_id, "name": r.from_area.name},
                          "to_area": {"id": r.to_area_id, "name": r.to_area.name}, "price": str(r.price), "is_active": r.is_active} for r in routes])

    def post(self, request):
        profile = services._driver_for(request.user)
        from_area = Area.objects.filter(pk=request.data.get("from_area"), is_active=True).first()
        to_area = Area.objects.filter(pk=request.data.get("to_area"), is_active=True).first()
        if from_area is None or to_area is None:
            raise DispatchError("Choose both areas from the list (or add a missing area first).")
        if from_area.pk == to_area.pk:
            raise DispatchError("Pick two different areas.")
        try:
            price = Decimal(str(request.data.get("price"))).quantize(Decimal("0.01"))
        except (InvalidOperation, ValueError):
            raise DispatchError("Enter the price in naira.")
        if not (MIN_ROUTE_PRICE <= price <= MAX_ROUTE_PRICE):
            raise DispatchError(f"The price must be between {MIN_ROUTE_PRICE:,.0f} and {MAX_ROUTE_PRICE:,.0f} naira.")
        route, created = DriverRoute.objects.update_or_create(
            driver=profile, from_area=from_area, to_area=to_area, defaults={"price": price, "is_active": True}
        )
        return Response({"id": route.id, "price": str(route.price)}, status=201 if created else 200)


class DriverRouteDetailView(DispatchView):
    throttle_scope = "dispatch-write"

    def delete(self, request, pk):
        profile = get_object_or_404(DriverProfile, user=request.user)
        route = get_object_or_404(DriverRoute, pk=pk, driver=profile)
        # Past orders keep the fee they were charged; the route only stops being offered.
        route.is_active = False
        route.save(update_fields=["is_active", "updated_at"])
        return Response(status=204)


class DriverJobsView(DispatchView):
    def get(self, request):
        profile = services._driver_for(request.user)
        offers = (
            DeliveryOffer.objects.filter(driver=profile, delivery__status__in=[OrderDelivery.Status.OFFERED, OrderDelivery.Status.ACCEPTED])
            .exclude(status__in=[DeliveryOffer.Status.DECLINED, DeliveryOffer.Status.WITHDRAWN])
            .select_related("delivery__pickup_area", "delivery__dropoff_area", "delivery__order__listing")
            .order_by("-delivery__offered_at")[:50]
        )
        # Jobs this driver was alerted to but lost still show, labelled "already accepted".
        open_jobs = [payloads.job_card(o) for o in offers if o.delivery.driver_id != profile.pk]
        mine = (
            OrderDelivery.objects.filter(driver=profile)
            .select_related("pickup_area", "dropoff_area", "order__listing", "order__buyer", "order__seller", "driver")
            .order_by("-accepted_at")[:50]
        )
        return Response({"open": open_jobs, "mine": [payloads.delivery_payload(d, request.user) for d in mine]})


class JobActionView(DispatchView):
    throttle_scope = "dispatch-write"
    action = None

    def post(self, request, pk):
        if self.action == "accept":
            delivery = services.accept_job(pk, request.user)
        elif self.action == "decline":
            services.decline_job(pk, request.user)
            return Response({"detail": "Declined."})
        elif self.action == "pickup":
            delivery = services.mark_picked_up(pk, request.user)
        return Response(payloads.delivery_payload(OrderDelivery.objects.get(pk=delivery.pk), request.user))


class JobDeliverView(DispatchView):
    parser_classes = [MultiPartParser, FormParser]
    throttle_scope = "handover-code"

    def post(self, request, pk):
        from django.conf import settings

        photo = request.FILES.get("photo")
        if photo is None:
            raise DispatchError("Take a photo of the delivered item.")
        if photo.size > settings.PROOF_PHOTO_MAX_BYTES:
            raise DispatchError("That photo is too large.")
        content = photo.read()
        kind = _sniff(content)
        if kind not in ("image/jpeg", "image/png"):
            raise DispatchError("The proof must be a JPG or PNG photo.")
        delivery = services.complete_delivery(pk, request.user, request.data.get("code"), content, kind)
        return Response(payloads.delivery_payload(OrderDelivery.objects.get(pk=delivery.pk), request.user))


# --- browsing and the seller's setup ---------------------------------------------------------------------


class DriversBrowseView(DispatchView):
    """Approved drivers and their prices, for a seller choosing who to offer. No phone numbers."""

    def get(self, request):
        routes = DriverRoute.objects.filter(is_active=True, driver__status=DriverProfile.Status.APPROVED).select_related("from_area", "to_area", "driver")
        if request.query_params.get("from"):
            routes = routes.filter(from_area_id=request.query_params["from"])
        if request.query_params.get("to"):
            routes = routes.filter(to_area_id=request.query_params["to"])
        grouped = {}
        for route in routes:
            grouped.setdefault(route.driver, []).append(route)
        return Response([payloads.public_driver(d, rs) for d, rs in grouped.items()])


class ListingDeliveryView(DispatchView):
    throttle_scope = "dispatch-write"

    def get_permissions(self):
        return [permissions.AllowAny()] if self.request.method == "GET" else super().get_permissions()

    def get_throttles(self):
        return [] if self.request.method == "GET" else super().get_throttles()

    def get(self, request, listing_id):
        listing = get_object_or_404(Listing, pk=listing_id)
        dropoff = Area.objects.filter(pk=request.query_params.get("to")).first() if request.query_params.get("to") else None
        found = services.options_for_buyer(listing, dropoff)
        if found is None:
            return Response({"enabled": False})
        options, drivers = found
        buyer_pays = lambda fee: str(services.split_fee(fee, options.payer)[0])  # noqa: E731
        return Response({
            "enabled": True,
            "payer": options.payer,
            "pickup_area": {"id": options.pickup_area_id, "name": options.pickup_area.name},
            "drivers": [
                {**payloads.public_driver(d, rs), "routes": [
                    {**r_, "you_pay": buyer_pays(r_["price"])} for r_ in payloads.public_driver(d, rs)["routes"]
                ]}
                for d, rs in drivers
            ],
        })

    def put(self, request, listing_id):
        listing = get_object_or_404(Listing, pk=listing_id)
        enabled = str(request.data.get("enabled", "true")).lower() in ("true", "1")
        pickup = Area.objects.filter(pk=request.data.get("pickup_area"), is_active=True).first()
        if pickup is None:
            raise DispatchError("Choose the area the item will be collected from.")
        services.set_listing_delivery(
            listing, request.user, enabled, request.data.get("payer", "buyer"), pickup, request.data.get("drivers") or []
        )
        return self.get(request, listing_id)


# --- one order's delivery ------------------------------------------------------------------------------------


def _order_for(request, pk):
    order = get_object_or_404(Order.objects.select_related("listing", "buyer", "seller"), pk=pk)
    driver = getattr(request.user, "driver_profile", None)
    is_assigned_driver = (
        driver is not None
        and OrderDelivery.objects.filter(order=order, driver=driver).exists()
    )
    if request.user.id not in (order.buyer_id, order.seller_id) and not is_assigned_driver and not request.user.is_staff:
        from rest_framework.exceptions import NotFound

        raise NotFound()
    return order


class OrderDeliveryView(DispatchView):
    throttle_scope = "dispatch-write"

    def get(self, request, pk):
        order = _order_for(request, pk)
        delivery = OrderDelivery.objects.filter(order=order).select_related("pickup_area", "dropoff_area", "driver", "order__listing", "order__buyer", "order__seller").first()
        if delivery is None:
            return JsonResponse(None, safe=False)
        return Response(payloads.delivery_payload(delivery, request.user))

    def post(self, request, pk):
        """Buyer, before paying: pick where it goes and whose price."""
        order = _order_for(request, pk)
        dropoff = Area.objects.filter(pk=request.data.get("dropoff_area"), is_active=True).first()
        driver = DriverProfile.objects.filter(pk=request.data.get("driver")).first()
        if dropoff is None or driver is None:
            raise DispatchError("Choose where it should go and which driver's price you want.")
        delivery = services.choose_delivery(order, request.user, dropoff, driver, request.data.get("dropoff_note", ""))
        return Response(payloads.delivery_payload(delivery, request.user), status=201)

    def delete(self, request, pk):
        services.clear_delivery(_order_for(request, pk), request.user)
        return Response(status=204)


class OrderReassignView(DispatchView):
    throttle_scope = "dispatch-write"

    def post(self, request, pk):
        delivery = services.reassign(_order_for(request, pk), request.user, request.data.get("add_drivers") or [])
        return Response(payloads.delivery_payload(delivery, request.user))


class OrderProofView(DispatchView):
    """The delivery photo, for the two people on the order (and staff in a dispute)."""

    def get(self, request, pk):
        order = _order_for(request, pk)
        delivery = get_object_or_404(OrderDelivery, order=order)
        if not delivery.proof_photo:
            return Response({"detail": "No proof photo yet."}, status=404)
        response = HttpResponse(bytes(delivery.proof_photo), content_type=delivery.proof_content_type or "image/jpeg")
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response
