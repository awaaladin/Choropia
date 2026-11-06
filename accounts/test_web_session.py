from django.test import TestCase

from accounts.models import User


class WebSessionCookieTests(TestCase):
    def setUp(self):
        User.objects.create_user("web@example.com", "pw12345!", first_name="Web")
        self.web = {"HTTP_X_CLIENT": "web"}

    def _login(self, **extra):
        return self.client.post("/api/v1/auth/login/", {"identifier": "web@example.com", "password": "pw12345!"}, content_type="application/json", **extra)

    def test_web_login_puts_the_refresh_token_in_an_httponly_cookie_not_the_body(self):
        r = self._login(**self.web)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIn("access", r.json())
        self.assertNotIn("refresh", r.json())
        cookie = r.cookies["choropia_rt"]
        self.assertTrue(cookie["httponly"])
        self.assertEqual(cookie["samesite"], "Strict")
        self.assertEqual(cookie["path"], "/api/v1/auth/")

    def test_the_app_still_gets_the_refresh_token_in_the_body(self):
        r = self._login()
        self.assertIn("refresh", r.json())
        self.assertNotIn("choropia_rt", r.cookies)

    def test_refresh_and_logout_work_from_the_cookie_alone(self):
        self._login(**self.web)  # the test client keeps the cookie
        r = self.client.post("/api/v1/auth/refresh/", {}, content_type="application/json", **self.web)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIn("access", r.json())
        self.assertNotIn("refresh", r.json())
        out = self.client.post("/api/v1/auth/logout/", {}, content_type="application/json", HTTP_AUTHORIZATION="Bearer " + r.json()["access"], **self.web)
        self.assertIn(out.status_code, (200, 204, 205))
        self.assertEqual(out.cookies["choropia_rt"].value, "")
        again = self.client.post("/api/v1/auth/refresh/", {}, content_type="application/json", **self.web)
        self.assertIn(again.status_code, (400, 401))

    def test_cookie_is_ignored_without_the_web_header(self):
        self._login(**self.web)
        r = self.client.post("/api/v1/auth/refresh/", {}, content_type="application/json")
        self.assertEqual(r.status_code, 400)
