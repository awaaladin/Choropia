"""The Choropia staff panel: a calm, branded replacement for the stock Django admin for day-to-day work (money,
orders, disputes, drivers, people). The Django admin stays available at its own address for deep edits."""
import csv
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.core.cache import cache
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.two_factor import check_second_factor, user_has_two_factor
from dispatch import crypto
from dispatch.models import DocumentAccessLog, DriverDocument, DriverProfile, OrderDelivery
from listings.models import Listing
from notifications import emails
from orders.models import Order
from orders.state_machine import InvalidOrderTransition, OrderStatus
from payments import payouts
from payments.models import Payment, Payout
from payments.paystack import PaystackError

from .access import audit, client_ip, staff_required, superuser_required
from .models import AuditLog

User = get_user_model()
ZERO = Decimal("0.00")
PENDING_2FA = "staff_pending_2fa"


def _sum(qs, field):
    return qs.aggregate(total=Sum(field))["total"] or ZERO


# --- signing in ----------------------------------------------------------------------------------


def _throttled(request):
    key = f"staff-login:{client_ip(request)}"
    return cache.get(key, 0) >= 10


def _failed(request):
    key = f"staff-login:{client_ip(request)}"
    cache.set(key, cache.get(key, 0) + 1, 15 * 60)


def login_view(request):
    if request.user.is_authenticated and request.user.is_staff:
        return redirect("staff:dashboard")
    error = ""
    if request.method == "POST":
        if _throttled(request):
            error = "Too many attempts. Wait a few minutes and try again."
        else:
            user = authenticate(request, username=request.POST.get("email", "").strip(), password=request.POST.get("password", ""))
            if user is None or not user.is_staff or not user.is_active:
                _failed(request)
                error = "That email and password do not match a staff account."
            elif user_has_two_factor(user):
                request.session[PENDING_2FA] = user.pk
                return redirect("staff:login_code")
            else:
                login(request, user)
                return redirect(request.GET.get("next") if (request.GET.get("next") or "").startswith("/staff/") else "staff:dashboard")
    return render(request, "staff/login.html", {"error": error})


def login_code_view(request):
    user_id = request.session.get(PENDING_2FA)
    user = User.objects.filter(pk=user_id, is_staff=True, is_active=True).first() if user_id else None
    if user is None:
        return redirect("staff:login")
    error = ""
    if request.method == "POST":
        if _throttled(request):
            error = "Too many attempts. Wait a few minutes and try again."
        elif check_second_factor(user.totp_device, request.POST.get("code", "")):
            request.session.pop(PENDING_2FA, None)
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            return redirect("staff:dashboard")
        else:
            _failed(request)
            error = "That code is not right."
    return render(request, "staff/login_code.html", {"error": error})


@require_POST
def logout_view(request):
    logout(request)
    return redirect("staff:login")


# --- dashboard -------------------------------------------------------------------------------------


@staff_required
def dashboard(request):
    now = timezone.now()
    week, month = now - timedelta(days=7), now - timedelta(days=30)
    owed = Payout.objects.filter(status__in=[Payout.Status.AWAITING_ACCOUNT, Payout.Status.PENDING, Payout.Status.NEEDS_ATTENTION])
    attention = Payout.objects.filter(status=Payout.Status.NEEDS_ATTENTION)
    paid_payouts = Payout.objects.filter(status=Payout.Status.SUCCESS)
    context = {
        "held": _sum(Payment.objects.filter(status=Payment.Status.PAID_HELD), "amount"),
        "held_count": Payment.objects.filter(status=Payment.Status.PAID_HELD).count(),
        "owed": _sum(owed, "net_amount"),
        "owed_count": owed.count(),
        "attention_count": attention.count(),
        "commission_earned": _sum(paid_payouts, "commission_amount"),
        "paid_out": _sum(paid_payouts, "net_amount"),
        "collected_30d": _sum(Payment.objects.filter(status__in=[Payment.Status.PAID_HELD, Payment.Status.RELEASED], paid_at__gte=month), "amount"),
        "orders_7d": Order.objects.filter(created_at__gte=week).count(),
        "new_users_7d": User.objects.filter(date_joined__gte=week).count(),
        "disputes": Order.objects.filter(status=OrderStatus.DISPUTED).select_related("listing", "buyer", "seller")[:6],
        "disputes_count": Order.objects.filter(status=OrderStatus.DISPUTED).count(),
        "drivers_pending": DriverProfile.objects.filter(status=DriverProfile.Status.PENDING).order_by("created_at")[:6],
        "drivers_pending_count": DriverProfile.objects.filter(status=DriverProfile.Status.PENDING).count(),
        "attention": attention.select_related("seller", "payment__order").order_by("updated_at")[:6],
        "waiting_driver": OrderDelivery.objects.filter(status=OrderDelivery.Status.OFFERED).count(),
        "payouts_enabled": settings.PAYOUTS_ENABLED,
    }
    return render(request, "staff/dashboard.html", {"nav": "dashboard", **context})


# --- payouts -------------------------------------------------------------------------------------


PAYOUT_TABS = {
    "attention": ("Needs attention", [Payout.Status.NEEDS_ATTENTION]),
    "waiting": ("Waiting", [Payout.Status.AWAITING_ACCOUNT, Payout.Status.PENDING]),
    "processing": ("In progress", [Payout.Status.PROCESSING]),
    "paid": ("Paid", [Payout.Status.SUCCESS]),
}


@staff_required
def payout_list(request):
    tab = request.GET.get("tab", "attention")
    if tab not in PAYOUT_TABS:
        tab = "attention"
    qs = Payout.objects.filter(status__in=PAYOUT_TABS[tab][1]).select_related("seller", "payment__order__listing").order_by("-updated_at")
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(seller__email__icontains=q) | Q(payment__order__id__iexact=q.lstrip("#")) | Q(seller__first_name__icontains=q))
    counts = {key: Payout.objects.filter(status__in=value[1]).count() for key, value in PAYOUT_TABS.items()}
    tabs = [(key, value[0], counts[key]) for key, value in PAYOUT_TABS.items()]
    return render(request, "staff/payout_list.html", {"nav": "payouts", "tab": tab, "tabs": tabs, "payouts": qs[:100], "q": q})


@staff_required
def payout_detail(request, pk):
    payout = get_object_or_404(Payout.objects.select_related("seller", "payment__order__listing", "manual_paid_by"), pk=pk)
    return render(request, "staff/payout_detail.html", {
        "nav": "payouts", "payout": payout, "can_pay_by_hand": payout.status in (Payout.Status.AWAITING_ACCOUNT, Payout.Status.PENDING, Payout.Status.NEEDS_ATTENTION),
        "account": getattr(payout.seller, "payout_account", None),
    })


@superuser_required
@require_POST
def payout_reveal(request, pk):
    """Show the full bank details (fetched from Paystack) so a person can pay by hand. Logged."""
    payout = get_object_or_404(Payout.objects.select_related("seller", "payment__order__listing"), pk=pk)
    details, error = None, ""
    try:
        details = payouts.recipient_details(payout)
        audit(request, "payout.reveal_bank_details", f"payout {payout.pk}", f"for {payout.seller.email}")
    except (payouts.ManualPayoutError, PaystackError) as exc:
        error = str(exc)
    return render(request, "staff/payout_detail.html", {
        "nav": "payouts", "payout": payout, "details": details, "reveal_error": error,
        "can_pay_by_hand": payout.status in (Payout.Status.AWAITING_ACCOUNT, Payout.Status.PENDING, Payout.Status.NEEDS_ATTENTION),
        "account": getattr(payout.seller, "payout_account", None),
    })


@superuser_required
@require_POST
def payout_mark_paid(request, pk):
    try:
        payout = payouts.mark_paid_manually(pk, request.user, request.POST.get("reference", ""), request.POST.get("note", ""))
    except payouts.ManualPayoutError as exc:
        messages.error(request, str(exc))
    else:
        audit(request, "payout.mark_paid_by_hand", f"payout {payout.pk}", f"ref {payout.manual_reference}; {payout.net_amount} to {payout.seller.email}")
        messages.success(request, f"Marked as paid: {payout.net_amount} to {payout.seller.get_full_name()}. They have been told.")
    return redirect("staff:payout_detail", pk=pk)


@superuser_required
@require_POST
def payout_retry(request, pk):
    """Put a stuck payout back in the automatic queue."""
    with transaction.atomic():
        payout = get_object_or_404(Payout.objects.select_for_update(), pk=pk)
        if payout.status != Payout.Status.NEEDS_ATTENTION:
            messages.error(request, "Only payouts that need attention can be retried.")
            return redirect("staff:payout_detail", pk=pk)
        payout.status, payout.attempts, payout.failure_reason = Payout.Status.PENDING, 0, ""
        payout.save(update_fields=["status", "attempts", "failure_reason", "updated_at"])
        transaction.on_commit(lambda: payouts.process_payout_safely(pk))
    audit(request, "payout.retry", f"payout {pk}")
    messages.success(request, "Put back in the queue. It will be sent automatically if transfers are switched on.")
    return redirect("staff:payout_detail", pk=pk)


# --- money -------------------------------------------------------------------------------------------


def _range(request):
    key = request.GET.get("range", "30")
    days = {"7": 7, "30": 30, "90": 90}.get(key)
    return key if days else "all", (timezone.now() - timedelta(days=days)) if days else None


@staff_required
def money(request):
    key, since = _range(request)

    def within(qs, field):
        return qs.filter(**{f"{field}__gte": since}) if since else qs

    collected = within(Payment.objects.filter(status__in=[Payment.Status.PAID_HELD, Payment.Status.RELEASED, Payment.Status.REFUNDED]), "paid_at")
    refunded = within(Payment.objects.filter(status=Payment.Status.REFUNDED), "refunded_at")
    done = within(Payout.objects.filter(status=Payout.Status.SUCCESS), "completed_at")
    auto, by_hand = done.filter(manual_paid_at__isnull=True), done.filter(manual_paid_at__isnull=False)
    seller_done, driver_done = done.filter(kind=Payout.Kind.SELLER), done.filter(kind=Payout.Kind.DRIVER)
    owed = Payout.objects.exclude(status=Payout.Status.SUCCESS).filter(payment__status=Payment.Status.RELEASED)
    rows = [
        ("Collected from buyers", _sum(collected, "amount"), "Everything buyers paid in this period (item plus delivery)."),
        ("Refunded to buyers", _sum(refunded, "amount"), "Paid back through Paystack."),
        ("Paid to sellers", _sum(seller_done, "net_amount"), "After commission."),
        ("Paid to drivers", _sum(driver_done, "net_amount"), "After the driver commission."),
        ("Paid by hand", _sum(by_hand, "net_amount"), "Included in the two lines above: paid outside Paystack."),
        ("Commission earned", _sum(done, "commission_amount"), "Seller and driver commission on payouts completed in this period, before Paystack's own charges."),
        ("Still owed to people", _sum(owed, "net_amount"), "Released orders whose payout is not paid yet (now, not just this period)."),
        ("Held in escrow now", _sum(Payment.objects.filter(status=Payment.Status.PAID_HELD), "amount"), "Paid by buyers, not yet released."),
    ]
    return render(request, "staff/money.html", {"nav": "money", "rows": rows, "range": key, "auto_count": auto.count(), "hand_count": by_hand.count()})


@staff_required
def payouts_csv(request):
    """Every payout as a spreadsheet, for the accounts."""
    audit(request, "payouts.export_csv")
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="choropia-payouts.csv"'
    writer = csv.writer(response)
    writer.writerow(["id", "order", "kind", "payee", "gross", "commission", "delivery_deduction", "net", "status", "paid_by_hand", "manual_reference", "completed_at", "created_at"])
    for p in Payout.objects.select_related("seller", "payment").order_by("id").iterator():
        writer.writerow([p.pk, p.payment.order_id, p.kind, p.seller.email, p.gross_amount, p.commission_amount, p.delivery_deduction, p.net_amount, p.status,
                         "yes" if p.manual_paid_at else "", p.manual_reference, p.completed_at or "", p.created_at])
    return response


# --- orders and disputes --------------------------------------------------------------------------


@staff_required
def order_list(request):
    status = request.GET.get("status", "")
    qs = Order.objects.select_related("listing", "buyer", "seller").order_by("-created_at")
    if status in dict(OrderStatus.CHOICES):
        qs = qs.filter(status=status)
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(listing__title__icontains=q) | Q(buyer__email__icontains=q) | Q(seller__email__icontains=q) | Q(pk__iexact=q.lstrip("#")))
    return render(request, "staff/order_list.html", {"nav": "orders", "orders": qs[:100], "status": status, "statuses": OrderStatus.CHOICES, "q": q})


@staff_required
def order_detail(request, pk):
    order = get_object_or_404(Order.objects.select_related("listing", "buyer", "seller"), pk=pk)
    payment = getattr(order, "payment", None)
    return render(request, "staff/order_detail.html", {
        "nav": "orders", "order": order, "payment": payment, "history": order.history.select_related("actor").order_by("created_at"),
        "payouts": payment.payouts.select_related("seller") if payment else [], "delivery": getattr(order, "dispatch_delivery", None),
    })


@superuser_required
@require_POST
def order_resolve(request, pk):
    """Settle a disputed order: refund the buyer (real Paystack refund) or pay the seller."""
    from payments.services import refund_escrow, release_escrow

    refund = request.POST.get("resolution") == "refund"
    note = (request.POST.get("note") or "").strip()[:200]
    order = get_object_or_404(Order, pk=pk)
    try:
        with transaction.atomic():
            order = Order.objects.select_for_update().get(pk=pk)
            if order.status != OrderStatus.DISPUTED:
                raise InvalidOrderTransition(order.status, "resolved")
            if refund:
                order.transition_to(OrderStatus.REFUNDED, actor=request.user, note=f"Dispute resolved: buyer refunded. {note}".strip())
                refund_escrow(order)
            else:
                order.transition_to(OrderStatus.COMPLETED, actor=request.user, note=f"Dispute resolved: seller paid. {note}".strip())
                release_escrow(order, auto=False)
    except (PaystackError, InvalidOrderTransition, ValueError) as exc:
        messages.error(request, f"Nothing was changed: {exc}")
    else:
        audit(request, "order.resolve_dispute", f"order {pk}", ("refund buyer" if refund else "pay seller") + (f"; {note}" if note else ""))
        messages.success(request, "Dispute settled: " + ("the buyer is being refunded." if refund else "the seller will be paid."))
    return redirect("staff:order_detail", pk=pk)


# --- drivers -----------------------------------------------------------------------------------------


@staff_required
def driver_list(request):
    status = request.GET.get("status", "pending")
    if status not in dict(DriverProfile.Status.choices):
        status = "pending"
    drivers = DriverProfile.objects.filter(status=status).select_related("user").annotate(doc_count=Count("documents", distinct=True)).order_by("created_at")[:100]
    counts = {value: DriverProfile.objects.filter(status=value).count() for value, _ in DriverProfile.Status.choices}
    tabs = [(value, label, counts[value]) for value, label in DriverProfile.Status.choices]
    return render(request, "staff/driver_list.html", {"nav": "drivers", "drivers": drivers, "status": status, "tabs": tabs})


def _docs_complete(driver):
    have = set(driver.documents.values_list("kind", flat=True))
    return DriverDocument.is_complete(have)


@staff_required
def driver_detail(request, pk):
    driver = get_object_or_404(DriverProfile.objects.select_related("user"), pk=pk)
    return render(request, "staff/driver_detail.html", {
        "nav": "drivers", "driver": driver, "documents": driver.documents.order_by("kind"), "complete": _docs_complete(driver),
        "required": DriverDocument.REQUIRED, "routes": driver.routes.select_related("from_area", "to_area").filter(is_active=True),
        "jobs": driver.deliveries.select_related("order__listing").order_by("-created_at")[:10],
    })


@staff_required
def document_view(request, pk):
    """Opens one encrypted identity document. Every view is recorded twice (driver access log and the staff audit log)."""
    document = get_object_or_404(DriverDocument, pk=pk)
    try:
        content = crypto.decrypt(document.encrypted_data)
    except crypto.DocumentDecryptionError:
        return HttpResponse("This document cannot be decrypted with the current key.", status=500)
    DocumentAccessLog.objects.create(document=document, staff=request.user)
    audit(request, "driver.document_view", f"driver {document.driver_id}", document.kind)
    response = HttpResponse(content, content_type=document.content_type)
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    response["Content-Disposition"] = "inline"
    return response


@superuser_required
@require_POST
def driver_test_toggle(request, pk):
    driver = get_object_or_404(DriverProfile, pk=pk)
    driver.is_test = not driver.is_test
    driver.save(update_fields=["is_test", "updated_at"])
    audit(request, "driver.test_on" if driver.is_test else "driver.test_off", f"driver {driver.pk}", driver.full_name)
    messages.success(request, "Marked as a test account: sellers and buyers can't see or pick them." if driver.is_test else "No longer a test account: real sellers and buyers can see them.")
    return redirect("staff:driver_detail", pk=pk)


@staff_required
@require_POST
def driver_decide(request, pk):
    driver = get_object_or_404(DriverProfile.objects.select_related("user"), pk=pk)
    decision = request.POST.get("decision")
    note = (request.POST.get("note") or "").strip()[:300]
    if decision == "approve":
        if not _docs_complete(driver):
            messages.error(request, "All four documents must be uploaded before approving.")
            return redirect("staff:driver_detail", pk=pk)
        status, text, note = DriverProfile.Status.APPROVED, "approved", ""
        emails.send_dispatch_notice(driver.user, "You are approved as a Choropia driver", "You are approved",
                                    "Your documents have been checked. Add the routes you serve and your prices, and sellers can start choosing you.", "/driver")
    elif decision == "reject":
        status, text = DriverProfile.Status.REJECTED, "rejected"
        note = note or "We could not verify your documents. Please re-upload clear photos and apply again."
        emails.send_dispatch_notice(driver.user, "Your driver application", "We could not approve your application", note, "/driver")
    elif decision == "suspend":
        status, text = DriverProfile.Status.SUSPENDED, "suspended"
        note = note or "Your driver account is suspended. Contact support."
    else:
        raise Http404
    driver.status, driver.review_note, driver.reviewed_at, driver.reviewed_by = status, note, timezone.now(), request.user
    driver.save()
    audit(request, f"driver.{text}", f"driver {driver.pk}", driver.full_name)
    messages.success(request, f"{driver.full_name} {text}.")
    return redirect("staff:driver_detail", pk=pk)


# --- people and listings ---------------------------------------------------------------------------------


@staff_required
def user_list(request):
    q = request.GET.get("q", "").strip()
    qs = User.objects.order_by("-date_joined")
    if q:
        qs = qs.filter(Q(email__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(phone_number__icontains=q))
    return render(request, "staff/user_list.html", {"nav": "people", "users": qs[:100], "q": q})


@staff_required
def user_detail(request, pk):
    person = get_object_or_404(User, pk=pk)
    return render(request, "staff/user_detail.html", {
        "nav": "people", "person": person,
        "purchases": person.purchases.select_related("listing").order_by("-created_at")[:8],
        "sales": person.sales.select_related("listing").order_by("-created_at")[:8],
        "listings": person.listings.order_by("-created_at")[:8],
    })


@superuser_required
@require_POST
def user_toggle(request, pk):
    person = get_object_or_404(User, pk=pk)
    if person.pk == request.user.pk or person.is_superuser:
        messages.error(request, "You cannot suspend yourself or another superuser here.")
        return redirect("staff:user_detail", pk=pk)
    person.is_active = not person.is_active
    person.save(update_fields=["is_active"])
    audit(request, "user.reactivate" if person.is_active else "user.suspend", f"user {person.pk}", person.email)
    messages.success(request, f"{person.email} is now {'active' if person.is_active else 'suspended (they cannot sign in)'}.")
    return redirect("staff:user_detail", pk=pk)


@staff_required
@require_POST
def user_verify_seller(request, pk):
    """Marks a seller as verified (lower fee on the first two bands, see payments/fees.py) or takes it away.
    Live offers keep the status they were made with."""
    from django.utils import timezone

    person = get_object_or_404(User.objects.select_related("profile"), pk=pk)
    if person.pk == request.user.pk:
        messages.error(request, "Ask another staff member to verify your own account.")
        return redirect("staff:user_detail", pk=pk)
    profile = person.profile
    profile.seller_verified = not profile.seller_verified
    profile.seller_verified_at = timezone.now() if profile.seller_verified else None
    profile.save(update_fields=["seller_verified", "seller_verified_at", "updated_at"])
    audit(request, "seller.verify" if profile.seller_verified else "seller.unverify", f"user {person.pk}", person.email)
    messages.success(request, f"{person.email} is {'now a verified seller' if profile.seller_verified else 'no longer a verified seller'}.")
    return redirect("staff:user_detail", pk=pk)


@staff_required
def listing_list(request):
    q = request.GET.get("q", "").strip()
    qs = Listing.objects.select_related("owner").order_by("-created_at")
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(owner__email__icontains=q))
    return render(request, "staff/listing_list.html", {"nav": "listings", "listings": qs[:100], "q": q})


@staff_required
@require_POST
def listing_toggle(request, pk):
    listing = get_object_or_404(Listing, pk=pk)
    if listing.status == Listing.Status.SOLD:
        messages.error(request, "A sold listing cannot be changed here.")
    else:
        listing.status = Listing.Status.ACTIVE if listing.status == Listing.Status.REMOVED else Listing.Status.REMOVED
        listing.save(update_fields=["status", "updated_at"])
        audit(request, f"listing.{listing.status}", f"listing {listing.pk}", listing.title[:80])
        messages.success(request, f"“{listing.title}” is now {listing.status}.")
    return redirect(request.POST.get("back") if (request.POST.get("back") or "").startswith("/staff/") else "staff:listing_list")


@staff_required
def audit_log(request):
    return render(request, "staff/audit.html", {"nav": "audit", "entries": AuditLog.objects.select_related("staff")[:200]})


# --- the deals board: who is paying whom, and where each deal stands -------------------------------------------------------


def describe_deal(order):
    """(next step for you, needs_you) in plain words, for the manual-escrow days."""
    payment = getattr(order, "payment", None)
    delivery = getattr(order, "dispatch_delivery", None)
    seller_payout = payment.payouts.filter(kind=Payout.Kind.SELLER).first() if payment else None
    status = order.status
    if status == OrderStatus.PENDING_PAYMENT:
        return "Waiting for the buyer to pay.", False
    if status == OrderStatus.PAID_ESCROW:
        if delivery and delivery.status == OrderDelivery.Status.OFFERED:
            return "Buyer has paid. Waiting for a driver to accept the delivery.", False
        return "Buyer has paid and the money is held. Waiting for the seller to send it.", False
    if status in (OrderStatus.COURIER_ASSIGNED, OrderStatus.IN_TRANSIT):
        return "On its way to the buyer.", False
    if status == OrderStatus.DELIVERED:
        return "Delivered. Waiting for the buyer to confirm (or the automatic release).", False
    if status == OrderStatus.DISPUTED:
        return "Dispute open: decide who gets the money.", True
    if status in (OrderStatus.CONFIRMED, OrderStatus.COMPLETED):
        if seller_payout and seller_payout.status != Payout.Status.SUCCESS:
            return f"Buyer confirmed. Pay the seller {seller_payout.net_amount}.", True
        if payment and payment.status == Payment.Status.RELEASED and seller_payout is None:
            return "Released, payout being set up.", True
        return "Done. The seller has been paid.", False
    if status == OrderStatus.REFUNDED:
        return "Refunded to the buyer.", False
    return "Cancelled.", False


DEAL_TABS = {
    "needs": ("Needs you", None),
    "progress": ("In progress", [OrderStatus.PAID_ESCROW, OrderStatus.COURIER_ASSIGNED, OrderStatus.IN_TRANSIT, OrderStatus.DELIVERED]),
    "unpaid": ("Waiting for payment", [OrderStatus.PENDING_PAYMENT]),
    "done": ("Finished", [OrderStatus.COMPLETED, OrderStatus.CONFIRMED, OrderStatus.REFUNDED, OrderStatus.CANCELLED]),
}


@staff_required
def deals(request):
    tab = request.GET.get("tab", "needs")
    if tab not in DEAL_TABS:
        tab = "needs"
    base = Order.objects.select_related("listing", "buyer", "seller", "payment", "dispatch_delivery__driver", "dispatch_delivery__dropoff_area", "dispatch_delivery__pickup_area").order_by("-updated_at")
    q = request.GET.get("q", "").strip()
    if q:
        base = base.filter(Q(listing__title__icontains=q) | Q(buyer__email__icontains=q) | Q(seller__email__icontains=q) | Q(pk__iexact=q.lstrip("#")))
    rows = []
    for order in base[:300]:
        step, needs = describe_deal(order)
        rows.append({"order": order, "step": step, "needs": needs, "delivery": getattr(order, "dispatch_delivery", None), "payment": getattr(order, "payment", None)})
    if tab == "needs":
        shown = [r for r in rows if r["needs"]]
    else:
        statuses = DEAL_TABS[tab][1]
        shown = [r for r in rows if r["order"].status in statuses and not (tab == "done" and r["needs"])]
    counts = {
        "needs": sum(1 for r in rows if r["needs"]),
        "progress": sum(1 for r in rows if r["order"].status in DEAL_TABS["progress"][1]),
        "unpaid": sum(1 for r in rows if r["order"].status in DEAL_TABS["unpaid"][1]),
        "done": sum(1 for r in rows if r["order"].status in DEAL_TABS["done"][1] and not r["needs"]),
    }
    tabs = [(key, value[0], counts[key]) for key, value in DEAL_TABS.items()]
    return render(request, "staff/deals.html", {"nav": "deals", "tab": tab, "tabs": tabs, "rows": shown[:100], "q": q})


# --- who may sell during the pilot --------------------------------------------------------------------------------------------


@staff_required
def sellers(request):
    from .models import ApprovedSeller, SiteSettings

    return render(request, "staff/sellers.html", {
        "nav": "sellers", "setting": SiteSettings.load(),
        "approved": ApprovedSeller.objects.select_related("user").order_by("focus", "user__email"),
    })


@superuser_required
@require_POST
def seller_setting(request):
    from .models import SiteSettings

    setting = SiteSettings.load()
    setting.seller_approval_required = request.POST.get("on") == "1"
    setting.save()
    audit(request, "sellers.invite_only_on" if setting.seller_approval_required else "sellers.invite_only_off")
    messages.success(request, "Only approved sellers can post listings now." if setting.seller_approval_required else "Anyone can post listings again.")
    return redirect("staff:sellers")


@superuser_required
@require_POST
def seller_add(request):
    from .models import ApprovedSeller

    email = (request.POST.get("email") or "").strip().lower()
    person = User.objects.filter(email__iexact=email).first()
    if person is None:
        messages.error(request, "No account has that email. Ask them to sign up first, then add them.")
    else:
        ApprovedSeller.objects.update_or_create(user=person, defaults={"focus": (request.POST.get("focus") or "").strip()[:40], "added_by": request.user})
        audit(request, "sellers.approve", f"user {person.pk}", person.email)
        messages.success(request, f"{person.get_full_name()} can now sell.")
    return redirect("staff:sellers")


@superuser_required
@require_POST
def seller_remove(request, pk):
    from .models import ApprovedSeller

    approved = get_object_or_404(ApprovedSeller, pk=pk)
    audit(request, "sellers.remove", f"user {approved.user_id}", approved.user.email)
    approved.delete()
    messages.success(request, "Removed. Their existing listings stay up; they cannot post new ones.")
    return redirect("staff:sellers")


# ---- backup of the driver-document key (superusers only) -------------------------------------------------------------
KEY_ATTEMPTS = 5


def _key_page(request, revealed=None):
    from .models import KeyBackup

    response = render(request, "staff/key_backup.html", {
        "nav": "keys", "backup": KeyBackup.objects.select_related("created_by").first(), "configured": crypto.keys_configured(),
        "min_length": 14, "revealed": revealed,
    })
    response["Cache-Control"] = "private, no-store"
    return response


@superuser_required
def key_backup(request):
    return _key_page(request)


@superuser_required
@require_POST
def key_backup_create(request):
    from . import keybackup

    password = request.POST.get("password", "")
    passphrase = request.POST.get("passphrase", "")
    if not request.user.check_password(password):
        messages.error(request, "Your login password was not right.")
    elif passphrase != request.POST.get("passphrase2", ""):
        messages.error(request, "The two backup passphrases do not match.")
    elif passphrase == password:
        messages.error(request, "The backup passphrase must be different from your login password.")
    else:
        try:
            keybackup.create_backup(passphrase, request.user)
        except keybackup.BackupError as exc:
            messages.error(request, str(exc))
        else:
            audit(request, "keys.backup_created")
            messages.success(request, "Backup saved. Write the passphrase down and keep it somewhere safe: nobody can recover it for you.")
    return redirect("staff:key_backup")


@superuser_required
@require_POST
def key_backup_recover(request):
    from . import keybackup

    attempts_key = f"key-recover:{request.user.pk}"
    if cache.get(attempts_key, 0) >= KEY_ATTEMPTS:
        messages.error(request, "Too many wrong tries. Wait 15 minutes and try again.")
        return redirect("staff:key_backup")
    if not request.user.check_password(request.POST.get("password", "")):
        cache.set(attempts_key, cache.get(attempts_key, 0) + 1, 15 * 60)
        messages.error(request, "Your login password was not right.")
        return redirect("staff:key_backup")
    try:
        key = keybackup.recover_key(request.POST.get("passphrase", ""))
    except keybackup.BackupError as exc:
        cache.set(attempts_key, cache.get(attempts_key, 0) + 1, 15 * 60)
        messages.error(request, str(exc))
        return redirect("staff:key_backup")
    cache.delete(attempts_key)
    audit(request, "keys.recovered")
    return _key_page(request, revealed=key)


# ---- inbox: what people send us (contact form, reports of listings, reviews) ------------------------------------------------
@staff_required
def inbox(request):
    from moderation.models import ContactMessage, Report
    from reviews.models import Review

    return render(request, "staff/inbox.html", {
        "nav": "inbox",
        "messages_open": ContactMessage.objects.filter(handled=False).select_related("user")[:50],
        "messages_done": ContactMessage.objects.filter(handled=True)[:10],
        "reports_open": Report.objects.filter(status=Report.Status.PENDING).select_related("reporter", "content_type")[:50],
        "reports_done": Report.objects.exclude(status=Report.Status.PENDING).select_related("reporter", "content_type")[:10],
        "reviews": Review.objects.select_related("reviewer", "reviewee", "order__listing").order_by("-created_at")[:25],
    })


@staff_required
@require_POST
def contact_handled(request, pk):
    from moderation.models import ContactMessage

    message = get_object_or_404(ContactMessage, pk=pk)
    message.handled = True
    message.save(update_fields=["handled", "updated_at"])
    audit(request, "contact.handled", f"message {pk}")
    messages.success(request, "Marked as handled.")
    return redirect("staff:inbox")


@staff_required
@require_POST
def report_resolve(request, pk):
    from moderation.models import Report

    report = get_object_or_404(Report, pk=pk)
    decision = request.POST.get("decision")
    if decision not in ("reviewed", "actioned", "dismissed"):
        messages.error(request, "Choose what to do with the report.")
        return redirect("staff:inbox")
    report.status = decision
    report.resolution_note = (request.POST.get("note") or "")[:500]
    report.reviewed_by = request.user
    report.reviewed_at = timezone.now()
    report.save(update_fields=["status", "resolution_note", "reviewed_by", "reviewed_at", "updated_at"])
    audit(request, f"report.{decision}", f"report {pk}")
    messages.success(request, "Report updated.")
    return redirect("staff:inbox")
