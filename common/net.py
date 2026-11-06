"""The caller's real IP address.

X-Forwarded-For can be written by anyone, so it is never trusted. Vercel sets x-vercel-forwarded-for itself (a client cannot
override it); anywhere else the connection's own address is used."""


def client_ip(request):
    return (
        request.META.get("HTTP_X_VERCEL_FORWARDED_FOR", "").split(",")[0].strip()
        or request.META.get("REMOTE_ADDR")
        or None
    )
