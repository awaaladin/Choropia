"""A recoverable backup of the driver-document encryption key.

The key (DOCUMENT_ENCRYPTION_KEY) normally lives only in the server's environment. If that setting were ever lost, every stored
identity document would be unreadable for good. So a superuser can lock a copy of it with a second passphrase and keep that
copy in the database: the passphrase is stretched with PBKDF2 (600,000 rounds, per-backup random salt) into a key that encrypts
the document key. The passphrase itself is never stored. Recovering needs the passphrase, and the staff panel also asks for
the admin's login password and records the event."""
import base64
import os

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from django.conf import settings

from .models import KeyBackup

ITERATIONS = 600_000
MIN_PASSPHRASE = 14


class BackupError(Exception):
    pass


def _lock(passphrase: str, salt: bytes, iterations: int) -> Fernet:
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=iterations)
    return Fernet(base64.urlsafe_b64encode(kdf.derive(passphrase.encode("utf-8"))))


def create_backup(passphrase: str, user) -> KeyBackup:
    key = (settings.DOCUMENT_ENCRYPTION_KEYS or "").strip()
    if not key:
        raise BackupError("There is no document key set on the server to back up.")
    if len(passphrase) < MIN_PASSPHRASE:
        raise BackupError(f"The backup passphrase must be at least {MIN_PASSPHRASE} characters.")
    salt = os.urandom(16)
    wrapped = _lock(passphrase, salt, ITERATIONS).encrypt(key.encode("utf-8"))
    return KeyBackup.objects.create(salt=salt, iterations=ITERATIONS, wrapped_key=wrapped, created_by=user)


def recover_key(passphrase: str) -> str:
    backup = KeyBackup.objects.first()
    if backup is None:
        raise BackupError("No key backup has been made yet.")
    try:
        return _lock(passphrase, bytes(backup.salt), backup.iterations).decrypt(bytes(backup.wrapped_key)).decode("utf-8")
    except InvalidToken:
        raise BackupError("That passphrase does not open the backup.") from None
