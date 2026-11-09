import uuid

from django.core import signing

GUEST_LIKE_TOKEN_SALT = "social.guest-like.v1"
GUEST_LIKE_HEADER = "HTTP_X_GUEST_LIKE_TOKEN"


def issue_guest_like_token():
    return signing.dumps(str(uuid.uuid4()), salt=GUEST_LIKE_TOKEN_SALT, compress=True)


def guest_id_from_token(token):
    if not isinstance(token, str) or not token or len(token) > 512:
        raise ValueError("Invalid guest identity token.")
    try:
        return uuid.UUID(signing.loads(token, salt=GUEST_LIKE_TOKEN_SALT))
    except (signing.BadSignature, TypeError, ValueError) as exc:
        raise ValueError("Invalid guest identity token.") from exc


def guest_id_from_request(request):
    token = request.META.get(GUEST_LIKE_HEADER)
    if not token:
        return None
    try:
        return guest_id_from_token(token)
    except ValueError:
        return None
