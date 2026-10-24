"""
Sign in with Google.

The mobile/web client does Google's own sign-in UI, gets a Google ID token, and posts it here. We
verify it with Google (tokeninfo endpoint), then log in — or create — the matching Choropia user.
Disabled (503) until GOOGLE_OAUTH_CLIENT_ID is configured.

Account matching: first by the provider's stable subject id, then by verified email (so someone who
already registered with the same address gets linked, not duplicated), otherwise a new account.
"""
import requests
from django.conf import settings
from django.db import transaction
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import SocialAccount, User
from .two_factor import login_response

TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"
VALID_ISSUERS = ("accounts.google.com", "https://accounts.google.com")


class GoogleTokenError(Exception):
    pass


def verify_google_id_token(id_token: str, client_id: str) -> dict:
    """Returns the verified claims or raises GoogleTokenError with a user-safe message."""
    if not id_token:
        raise GoogleTokenError("Missing Google token.")
    try:
        response = requests.get(TOKENINFO_URL, params={"id_token": id_token}, timeout=10)
    except requests.RequestException:
        raise GoogleTokenError("Couldn't reach Google to verify your sign-in. Please try again.")
    if response.status_code != 200:
        raise GoogleTokenError("Google rejected this sign-in. Please try again.")

    claims = response.json()
    if claims.get("aud") != client_id:
        raise GoogleTokenError("This Google sign-in wasn't issued for Choropia.")
    if claims.get("iss") not in VALID_ISSUERS:
        raise GoogleTokenError("Untrusted Google token issuer.")
    if str(claims.get("email_verified")).lower() != "true":
        raise GoogleTokenError("Your Google email address isn't verified.")
    if not claims.get("sub") or not claims.get("email"):
        raise GoogleTokenError("Google didn't return an email address.")
    return claims


@transaction.atomic
def user_for_google_claims(claims: dict) -> User:
    uid = claims["sub"]
    email = claims["email"].strip().lower()

    linked = SocialAccount.objects.select_related("user").filter(provider="google", uid=uid).first()
    if linked:
        return linked.user

    user = User.objects.filter(email__iexact=email).first()
    if user is None:
        user = User(
            email=email,
            first_name=(claims.get("given_name") or "")[:100],
            last_name=(claims.get("family_name") or "")[:100],
        )
        user.set_unusable_password()
        user.save()  # Profile is created by the accounts post_save signal
    SocialAccount.objects.create(user=user, provider="google", uid=uid)
    # verify_google_id_token already required email_verified, so Google vouches for this address.
    user.profile.email_verified = True
    user.profile.save(update_fields=["email_verified", "updated_at"])
    return user


class GoogleLoginView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    throttle_scope = "auth"

    def post(self, request):
        client_id = getattr(settings, "GOOGLE_OAUTH_CLIENT_ID", "")
        if not client_id:
            return Response({"detail": "Google sign-in isn't available yet."}, status=503)

        try:
            claims = verify_google_id_token(request.data.get("id_token", ""), client_id)
        except GoogleTokenError as exc:
            return Response({"detail": str(exc)}, status=400)

        user = user_for_google_claims(claims)
        if not user.is_active:
            return Response({"detail": "This account is inactive."}, status=403)
        return Response(login_response(user))
