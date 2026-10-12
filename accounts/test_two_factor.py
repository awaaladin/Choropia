from django.core.cache import cache
from rest_framework.test import APIClient, APITestCase

from accounts import two_factor
from accounts.models import TOTPDevice, User

PASSWORD = "S3cure-passw0rd!"


class TwoFactorFlowTests(APITestCase):
    def setUp(self):
        cache.clear()  # the "auth" throttle scope is shared across tests
        self.addCleanup(cache.clear)
        self.user = User.objects.create_user("ada@example.com", PASSWORD, first_name="Ada")
        self.client = APIClient()

    def _login(self):
        return self.client.post("/api/v1/auth/login/", {"identifier": "ada@example.com", "password": PASSWORD})

    def _auth(self):
        tokens = self._login().json()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

    def _enable(self):
        """Runs setup + confirm and returns (secret, recovery_codes)."""
        self._auth()
        secret = self.client.post("/api/v1/auth/2fa/setup/").json()["secret"]
        confirm = self.client.post("/api/v1/auth/2fa/confirm/", {"code": two_factor.totp_code(secret)})
        self.assertEqual(confirm.status_code, 200)
        self.client.credentials()  # forget the token: later logins must go through the challenge
        return secret, confirm.json()["recovery_codes"]

    def test_rfc6238_reference_vector(self):
        # RFC 6238 appendix B, SHA-1, secret "12345678901234567890", T=59s -> 94287082 (6 digits: 287082).
        import base64

        secret = base64.b32encode(b"12345678901234567890").decode().rstrip("=")
        self.assertEqual(two_factor.totp_code(secret, step=59 // 30), "287082")

    def test_login_without_2fa_returns_tokens(self):
        data = self._login().json()
        self.assertIn("access", data)
        self.assertFalse(data["user"]["two_factor_enabled"])

    def test_setup_alone_does_not_change_login(self):
        self._auth()
        self.assertEqual(self.client.post("/api/v1/auth/2fa/setup/").status_code, 200)
        self.client.credentials()
        self.assertIn("access", self._login().json())  # not confirmed yet -> no challenge

    def test_confirm_rejects_wrong_code(self):
        self._auth()
        self.client.post("/api/v1/auth/2fa/setup/")
        wrong = self.client.post("/api/v1/auth/2fa/confirm/", {"code": "000000"})
        self.assertEqual(wrong.status_code, 400)
        self.assertFalse(TOTPDevice.objects.get(user=self.user).confirmed)

    def test_login_then_verify_issues_tokens(self):
        secret, _ = self._enable()
        first = self._login().json()
        self.assertTrue(first["two_factor_required"])
        self.assertNotIn("access", first)

        # The confirm step consumed the current time step; use the next one, as a real user would.
        next_code = two_factor.totp_code(secret, step=two_factor.current_step() + 1)
        done = self.client.post("/api/v1/auth/2fa/verify/", {"challenge": first["challenge"], "code": next_code})
        self.assertEqual(done.status_code, 200)
        self.assertIn("access", done.json())
        self.assertTrue(done.json()["user"]["two_factor_enabled"])

    def test_wrong_code_and_bad_challenge_are_rejected(self):
        self._enable()
        challenge = self._login().json()["challenge"]
        self.assertEqual(
            self.client.post("/api/v1/auth/2fa/verify/", {"challenge": challenge, "code": "123456"}).status_code, 400
        )
        self.assertEqual(
            self.client.post("/api/v1/auth/2fa/verify/", {"challenge": "garbage", "code": "123456"}).status_code, 400
        )

    def test_a_code_cannot_be_replayed(self):
        secret, _ = self._enable()
        code = two_factor.totp_code(secret, step=two_factor.current_step() + 1)
        challenge = self._login().json()["challenge"]
        self.assertEqual(self.client.post("/api/v1/auth/2fa/verify/", {"challenge": challenge, "code": code}).status_code, 200)
        challenge2 = self._login().json()["challenge"]
        replay = self.client.post("/api/v1/auth/2fa/verify/", {"challenge": challenge2, "code": code})
        self.assertEqual(replay.status_code, 400)

    def test_recovery_code_works_once(self):
        _, codes = self._enable()
        challenge = self._login().json()["challenge"]
        ok = self.client.post("/api/v1/auth/2fa/verify/", {"challenge": challenge, "code": codes[0]})
        self.assertEqual(ok.status_code, 200)
        again = self.client.post(
            "/api/v1/auth/2fa/verify/", {"challenge": self._login().json()["challenge"], "code": codes[0]}
        )
        self.assertEqual(again.status_code, 400)

    def test_disable_needs_password_and_code(self):
        secret, codes = self._enable()
        tokens = self.client.post(
            "/api/v1/auth/2fa/verify/",
            {"challenge": self._login().json()["challenge"], "code": codes[0]},
        ).json()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        bad_pw = self.client.post("/api/v1/auth/2fa/disable/", {"password": "nope", "code": codes[1]})
        self.assertEqual(bad_pw.status_code, 400)
        ok = self.client.post("/api/v1/auth/2fa/disable/", {"password": PASSWORD, "code": codes[1]})
        self.assertEqual(ok.status_code, 200)
        self.assertFalse(TOTPDevice.objects.filter(user=self.user).exists())
        self.client.credentials()
        self.assertIn("access", self._login().json())
