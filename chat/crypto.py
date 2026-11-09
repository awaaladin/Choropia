from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

ENCRYPTED_PREFIX = "fernet:v1:"


class MessageDecryptionError(Exception):
    pass


def _fernet():
    keys = [key.strip() for key in settings.CHAT_MESSAGE_ENCRYPTION_KEYS.split(",") if key.strip()]
    if not keys:
        raise ImproperlyConfigured(
            "CHAT_MESSAGE_ENCRYPTION_KEYS must be configured before chat messages can be stored."
        )
    try:
        return MultiFernet([Fernet(key.encode("ascii")) for key in keys])
    except (ValueError, TypeError, UnicodeEncodeError) as exc:
        raise ImproperlyConfigured("CHAT_MESSAGE_ENCRYPTION_KEYS contains an invalid Fernet key.") from exc


def encrypt_message(value: str) -> str:
    return ENCRYPTED_PREFIX + _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_message(value: str) -> str:
    try:
        token = value[len(ENCRYPTED_PREFIX) :].encode("ascii")
        return _fernet().decrypt(token).decode("utf-8")
    except (InvalidToken, UnicodeDecodeError, UnicodeEncodeError) as exc:
        raise MessageDecryptionError("The chat message could not be decrypted.") from exc
