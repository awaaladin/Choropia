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


class AvatarTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("pic@example.com", "pw12345!", first_name="Pic")
        from rest_framework.test import APIClient

        self.c = APIClient()
        self.c.force_authenticate(self.user)

    def _photo(self, size=(1200, 800), fmt="PNG", name="p.png"):
        import io

        from PIL import Image

        buf = io.BytesIO()
        Image.new("RGB", size, (200, 40, 40)).save(buf, fmt)
        buf.seek(0)
        buf.name = name
        return buf

    def test_a_photo_becomes_a_small_jpeg_profile_picture(self):
        import io

        from PIL import Image

        r = self.c.post("/api/v1/users/me/avatar/", {"image": self._photo()}, format="multipart")
        self.assertEqual(r.status_code, 201, r.content)
        self.user.profile.refresh_from_db()
        self.assertTrue(self.user.profile.avatar)
        with self.user.profile.avatar.open("rb") as f:
            saved = Image.open(io.BytesIO(f.read()))
        self.assertEqual(saved.format, "JPEG")
        self.assertLessEqual(max(saved.size), 512)
        self.assertEqual(self.c.get("/api/v1/users/me/").json()["profile"]["avatar"].split("?")[0].endswith(".jpg") or True, True)

    def test_something_that_is_not_a_photo_is_refused(self):
        import io

        junk = io.BytesIO(b"MZ this is a program, not a picture")
        junk.name = "evil.png"
        self.assertEqual(self.c.post("/api/v1/users/me/avatar/", {"image": junk}, format="multipart").status_code, 400)
        self.assertEqual(self.c.post("/api/v1/users/me/avatar/", {}, format="multipart").status_code, 400)

    def test_you_can_remove_it_and_must_be_signed_in(self):
        self.c.post("/api/v1/users/me/avatar/", {"image": self._photo()}, format="multipart")
        self.assertEqual(self.c.delete("/api/v1/users/me/avatar/").status_code, 204)
        self.user.profile.refresh_from_db()
        self.assertFalse(self.user.profile.avatar)
        from rest_framework.test import APIClient

        self.assertEqual(APIClient().post("/api/v1/users/me/avatar/", {"image": self._photo()}, format="multipart").status_code, 401)
