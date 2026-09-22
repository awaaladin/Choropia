"""
JWT authentication for Django Channels WebSocket consumers.

Channels has no session/cookie to rely on (and we deliberately don't want one —
the API is 100% token-based for both the Kotlin app and the web frontend), so
the access token is passed as a query string parameter on the socket URL, e.g.:

    wss://host/ws/chat/<conversation_id>/?token=<access_token>

and validated here the same way SimpleJWT validates it for normal HTTP requests.
"""
from urllib.parse import parse_qs

from channels.auth import AuthMiddlewareStack
from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import AccessToken


@database_sync_to_async
def get_user_from_token(token):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    try:
        validated_token = AccessToken(token)
        user = User.objects.get(id=validated_token["user_id"])
        return user
    except (InvalidToken, TokenError, User.DoesNotExist, KeyError):
        return AnonymousUser()


class JWTAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        query_string = parse_qs(scope.get("query_string", b"").decode())
        token = query_string.get("token", [None])[0]

        scope["user"] = await get_user_from_token(token) if token else AnonymousUser()
        return await super().__call__(scope, receive, send)


def JWTAuthMiddlewareStack(inner):
    """Falls back through Channels' session auth stack, then overrides with JWT."""
    return JWTAuthMiddleware(AuthMiddlewareStack(inner))
