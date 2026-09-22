import re

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

User = get_user_model()


@override_settings(PASSWORD_RESET_URL_BASE="http://testserver/reset-password/")
class PasswordResetTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(email="reset@example.com", password="OldPassw0rd!")

    def _request_link_params(self):
        self.client.post("/api/v1/auth/password-reset/", {"email": "reset@example.com"})
        body = mail.outbox[0].body
        return re.search(r"uid=([^&\s]+)&token=([^\s]+)", body).groups()

    def test_request_sends_email_with_link_for_registered_address(self):
        response = self.client.post("/api/v1/auth/password-reset/", {"email": "reset@example.com"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("http://testserver/reset-password/?uid=", mail.outbox[0].body)

    def test_request_for_unknown_address_looks_identical_and_sends_nothing(self):
        response = self.client.post("/api/v1/auth/password-reset/", {"email": "nobody@example.com"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)

    def test_confirm_with_valid_token_changes_password_and_allows_login(self):
        uid, token = self._request_link_params()

        response = self.client.post(
            "/api/v1/auth/password-reset/confirm/",
            {"uid": uid, "token": token, "password": "BrandNewPassw0rd!"},
        )

        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("BrandNewPassw0rd!"))

    def test_token_cannot_be_reused_after_password_changes(self):
        uid, token = self._request_link_params()
        payload = {"uid": uid, "token": token, "password": "BrandNewPassw0rd!"}
        self.client.post("/api/v1/auth/password-reset/confirm/", payload)

        second = self.client.post(
            "/api/v1/auth/password-reset/confirm/", {**payload, "password": "AnotherPassw0rd!"}
        )

        self.assertEqual(second.status_code, 400)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("BrandNewPassw0rd!"))

    def test_confirm_rejects_bad_token_and_weak_password(self):
        uid, token = self._request_link_params()

        bad_token = self.client.post(
            "/api/v1/auth/password-reset/confirm/",
            {"uid": uid, "token": "not-a-real-token", "password": "BrandNewPassw0rd!"},
        )
        weak = self.client.post(
            "/api/v1/auth/password-reset/confirm/", {"uid": uid, "token": token, "password": "123"}
        )

        self.assertEqual(bad_token.status_code, 400)
        self.assertEqual(weak.status_code, 400)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("OldPassw0rd!"))
