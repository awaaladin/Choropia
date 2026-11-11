"""
Public, unguessable identifiers for things that appear in links (listings, chats, orders).

Database rows keep their integer primary keys internally. Links show a random code instead, so nobody can count how
many listings or orders Choropia has, or walk through them by trying 1, 2, 3. Codes are not a security boundary on
their own: every API still checks who is asking.

10 characters of lowercase letters and digits (no look-alikes) ≈ 2^50 possibilities.
"""
import re
import secrets

from django.utils.text import slugify

ALPHABET = "23456789abcdefghjkmnpqrstuvwxyz"  # no 0/o, 1/l/i
LENGTH = 10
CODE_RE = re.compile(rf"^[{ALPHABET}]{{{LENGTH}}}$")


def new_public_id() -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(LENGTH))


def is_public_id(value) -> bool:
    return isinstance(value, str) and bool(CODE_RE.match(value))


def code_from_ref(ref: str) -> str:
    """Accepts a bare code or a "title-slug-code" reference (listings) and returns the code part."""
    return str(ref or "").rsplit("-", 1)[-1].lower()


def listing_slug(title: str, public_id: str) -> str:
    """"skirt-k7f3q9x2ab": a readable title for people and search engines, the code for us."""
    words = slugify(title or "")[:48].strip("-")
    return f"{words}-{public_id}" if words else public_id


def lookup_kwargs(ref) -> dict:
    """ORM filter for a reference that may be an old numeric id or a public code (with or without a title slug)."""
    text = str(ref or "").strip()
    if text.isdigit():
        return {"pk": int(text)}
    code = code_from_ref(text)
    return {"public_id": code} if is_public_id(code) else {"pk": -1}


class PublicIdLookupMixin:
    """For DRF viewsets: detail routes accept the old numeric id or the public code (`/listings/k7f3q9x2ab/`, or with a
    title slug in front). Queryset scoping and object permissions are applied exactly as before."""

    def get_object(self):
        from django.shortcuts import get_object_or_404

        queryset = self.filter_queryset(self.get_queryset())
        ref = self.kwargs[self.lookup_url_kwarg or self.lookup_field]
        obj = get_object_or_404(queryset, **lookup_kwargs(ref))
        self.check_object_permissions(self.request, obj)
        return obj
