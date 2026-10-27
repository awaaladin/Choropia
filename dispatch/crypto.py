"""Encryption for drivers' identity documents.

Files are encrypted here, in the application, before they reach the database, so a database leak
or a backup on its own reveals nothing: reading a document needs the key, which lives only in the
environment (DOCUMENT_ENCRYPTION_KEY). Fernet = AES-128-CBC + HMAC-SHA256 (authenticated, so a
tampered document fails to decrypt instead of returning garbage).

DOCUMENT_ENCRYPTION_KEY may hold several comma-separated keys: the first one encrypts new files
and every key can still decrypt, which is how a key is rotated without losing old documents."""
from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


class DocumentDecryptionError(Exception):
    pass


def _fernet():
    keys = [k.strip() for k in (settings.DOCUMENT_ENCRYPTION_KEYS or "").split(",") if k.strip()]
    if not keys:
        raise ImproperlyConfigured("DOCUMENT_ENCRYPTION_KEY is not set, so driver documents cannot be stored.")
    try:
        return MultiFernet([Fernet(k.encode()) for k in keys])
    except (ValueError, TypeError) as exc:
        raise ImproperlyConfigured("DOCUMENT_ENCRYPTION_KEY is not a valid Fernet key.") from exc


def encrypt(data: bytes) -> bytes:
    return _fernet().encrypt(data)


def decrypt(token: bytes) -> bytes:
    try:
        return _fernet().decrypt(bytes(token))
    except InvalidToken as exc:
        raise DocumentDecryptionError("The document could not be decrypted (wrong key or damaged data).") from exc


def keys_configured() -> bool:
    try:
        _fernet()
        return True
    except ImproperlyConfigured:
        return False
