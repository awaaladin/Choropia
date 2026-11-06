"""Who may use the staff panel, and the record of what they did.

* Everyone needs a staff account (is_staff). A staff account with 2-step verification switched on must also enter the
  code from their authenticator app to get in (a password alone cannot move money).
* Actions that move money or show private bank details need a superuser.
* Every such action is written to the audit log."""
from functools import wraps

from django.contrib.auth import REDIRECT_FIELD_NAME
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.shortcuts import resolve_url

from .models import AuditLog


from common.net import client_ip  # noqa: E402,F401  (re-exported: the staff panel imports it from here)


def audit(request, action, target="", detail=""):
    AuditLog.objects.create(staff=request.user, action=action, target=str(target)[:80], detail=str(detail)[:300], ip_address=client_ip(request))


def staff_required(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path(), resolve_url("staff:login"), REDIRECT_FIELD_NAME)
        if not (request.user.is_staff and request.user.is_active):
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return wrapper


def superuser_required(view):
    """Money-moving and private-data actions: staff who are not superusers can look but not touch."""

    @wraps(view)
    @staff_required
    def wrapper(request, *args, **kwargs):
        if not request.user.is_superuser:
            raise PermissionDenied("Only a superuser can do this.")
        return view(request, *args, **kwargs)

    return wrapper
