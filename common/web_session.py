"""Keeps the website's long-lived refresh token out of reach of page scripts.

The browser app sends `X-Client: web`. For those requests only:
  * login / register / Google / 2-step / refresh responses carry the refresh token in an HttpOnly cookie instead of the JSON
    body, so an injected script can never read it;
  * refresh and logout read it back from that cookie.
The Android app never sends the header and keeps receiving tokens in the body, exactly as before. The cookie is SameSite=Strict
and only works on /api/v1/auth/, and the custom header cannot be set by another website, so it cannot be abused cross-site."""
import json
from io import BytesIO

from django.conf import settings

COOKIE = "choropia_rt"
COOKIE_PATH = "/api/v1/auth/"
ISSUE_PATHS = {
    "/api/v1/auth/login/",
    "/api/v1/auth/register/",
    "/api/v1/auth/google/",
    "/api/v1/auth/2fa/verify/",
    "/api/v1/auth/refresh/",
}
READ_PATHS = {"/api/v1/auth/refresh/", "/api/v1/auth/logout/"}
CLEAR_PATHS = {"/api/v1/auth/logout/", "/api/v1/auth/logout-all/"}


class WebSessionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        web = request.headers.get("X-Client") == "web"
        path = request.path
        if web and path in READ_PATHS and request.COOKIES.get(COOKIE):
            self._put_refresh_in_body(request)

        response = self.get_response(request)

        if web:
            if path in ISSUE_PATHS and response.status_code in (200, 201):
                self._move_refresh_to_cookie(response)
            elif path in CLEAR_PATHS or (path in READ_PATHS and response.status_code in (400, 401)):
                response.delete_cookie(COOKIE, path=COOKIE_PATH)
        return response

    @staticmethod
    def _put_refresh_in_body(request):
        try:
            data = json.loads(request.body or b"{}")
        except ValueError:
            return
        if not isinstance(data, dict) or data.get("refresh"):
            return
        data["refresh"] = request.COOKIES[COOKIE]
        body = json.dumps(data).encode()
        request._body = body
        request._stream = BytesIO(body)
        request.META["CONTENT_LENGTH"] = str(len(body))

    @staticmethod
    def _move_refresh_to_cookie(response):
        try:
            data = json.loads(response.content)
        except ValueError:
            return
        refresh = data.pop("refresh", None) if isinstance(data, dict) else None
        if not refresh:
            return
        response.content = json.dumps(data).encode()
        response["Content-Length"] = str(len(response.content))
        response.set_cookie(
            COOKIE,
            refresh,
            max_age=int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds()),
            path=COOKIE_PATH,
            secure=not settings.DEBUG,
            httponly=True,
            samesite="Strict",
        )
