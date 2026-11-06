from django.core.cache import cache
from django.test import TestCase, override_settings

from accounts.models import User
from staffpanel import keybackup
from staffpanel.models import AuditLog, KeyBackup

KEY = "0g4yZ3m0c0nF0c1c8Jr3Oq8o2m3m3VbYQb0xv4b2xGc="


@override_settings(DOCUMENT_ENCRYPTION_KEYS=KEY)
class KeyBackupTests(TestCase):
    def setUp(self):
        cache.clear()  # the wrong-try counter lives in the cache
        self.boss = User.objects.create_superuser("boss@example.com", "login-password-123")
        self.client.force_login(self.boss)

    def _make(self, passphrase="a long second passphrase", password="login-password-123"):
        return self.client.post(
            "/staff/keys/create/", {"passphrase": passphrase, "passphrase2": passphrase, "password": password}
        )

    def test_backup_round_trips_and_stores_no_plaintext(self):
        self._make()
        backup = KeyBackup.objects.get()
        self.assertNotIn(KEY.encode(), bytes(backup.wrapped_key))
        self.assertEqual(keybackup.recover_key("a long second passphrase"), KEY)
        with self.assertRaises(keybackup.BackupError):
            keybackup.recover_key("a completely wrong passphrase")
        self.assertTrue(AuditLog.objects.filter(action="keys.backup_created").exists())

    def test_needs_the_login_password_a_long_passphrase_and_a_different_one(self):
        self._make(password="wrong-password")
        self._make(passphrase="short")
        self._make(passphrase="login-password-123")
        self.assertFalse(KeyBackup.objects.exists())

    def test_recovery_shows_the_key_once_and_is_logged(self):
        self._make()
        wrong = self.client.post("/staff/keys/recover/", {"passphrase": "nope nope nope nope", "password": "login-password-123"})
        self.assertNotContains(wrong, KEY, status_code=302)
        ok = self.client.post("/staff/keys/recover/", {"passphrase": "a long second passphrase", "password": "login-password-123"})
        self.assertContains(ok, KEY)
        self.assertEqual(ok["Cache-Control"], "private, no-store")
        self.assertTrue(AuditLog.objects.filter(action="keys.recovered").exists())

    def test_locks_after_five_wrong_tries_and_is_superuser_only(self):
        self._make()
        for _ in range(5):
            self.client.post("/staff/keys/recover/", {"passphrase": "wrong wrong wrong", "password": "login-password-123"})
        locked = self.client.post("/staff/keys/recover/", {"passphrase": "a long second passphrase", "password": "login-password-123"})
        self.assertEqual(locked.status_code, 302)
        staff = User.objects.create_user("staff@example.com", "pw12345!", is_staff=True)
        self.client.force_login(staff)
        self.assertIn(self.client.get("/staff/keys/").status_code, (302, 403))
