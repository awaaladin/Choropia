from unittest import mock

from django.core.cache import cache
from django.test import override_settings
from rest_framework.test import APIClient, APITestCase

from accounts.models import SocialAccount, User

CLIENT_ID = "test-client.apps.googleusercontent.com"


def google_ok(**overrides):
    claims = {
        "aud": CLIENT_ID,
        "iss": "https://accounts.google.com",
        "sub": "1234567890",
        "email": "grace@example.com",
        "email_verified": "true",
        "given_name": "Grace",
        "family_name": "Hopper",
    }
    claims.update(overrides)
    response = mock.Mock(status_code=200)
    response.json.return_value = claims
    return response


@override_settings(GOOGLE_OAUTH_CLIENT_ID=CLIENT_ID)
class GoogleLoginTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.client = APIClient()
        self.url = "/api/v1/auth/google/"

    @override_settings(GOOGLE_OAUTH_CLIENT_ID="")
    def test_disabled_until_configured(self):
        self.assertEqual(self.client.post(self.url, {"id_token": "x"}).status_code, 503)

    @mock.patch("accounts.google.requests.get")
    def test_creates_a_user_and_returns_tokens(self, get):
        get.return_value = google_ok()
        response = self.client.post(self.url, {"id_token": "valid"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.json())
        user = User.objects.get(email="grace@example.com")
        self.assertEqual(user.first_name, "Grace")
        self.assertFalse(user.has_usable_password())
        self.assertTrue(SocialAccount.objects.filter(user=user, provider="google", uid="1234567890").exists())

    @mock.patch("accounts.google.requests.get")
    def test_links_an_existing_account_by_verified_email(self, get):
        existing = User.objects.create_user("grace@example.com", "pw-12345-pw")
        get.return_value = google_ok()
        self.assertEqual(self.client.post(self.url, {"id_token": "valid"}).status_code, 200)
        self.assertEqual(User.objects.filter(email="grace@example.com").count(), 1)
        self.assertTrue(SocialAccount.objects.filter(user=existing).exists())

    @mock.patch("accounts.google.requests.get")
    def test_second_login_reuses_the_linked_identity(self, get):
        get.return_value = google_ok()
        self.client.post(self.url, {"id_token": "valid"})
        # Even if Google later reports a different email for the same subject, we match on subject.
        get.return_value = google_ok(email="renamed@example.com")
        self.assertEqual(self.client.post(self.url, {"id_token": "valid"}).status_code, 200)
        self.assertEqual(User.objects.count(), 1)

    @mock.patch("accounts.google.requests.get")
    def test_rejects_token_for_another_app(self, get):
        get.return_value = google_ok(aud="someone-elses-client")
        self.assertEqual(self.client.post(self.url, {"id_token": "t"}).status_code, 400)
        self.assertEqual(User.objects.count(), 0)

    @mock.patch("accounts.google.requests.get")
    def test_rejects_unverified_email(self, get):
        get.return_value = google_ok(email_verified="false")
        self.assertEqual(self.client.post(self.url, {"id_token": "t"}).status_code, 400)

    @mock.patch("accounts.google.requests.get")
    def test_rejects_token_google_refuses(self, get):
        get.return_value = mock.Mock(status_code=400)
        self.assertEqual(self.client.post(self.url, {"id_token": "bad"}).status_code, 400)

    @mock.patch("accounts.google.requests.get")
    def test_google_login_respects_two_factor(self, get):
        from accounts import two_factor
        from accounts.models import TOTPDevice

        user = User.objects.create_user("grace@example.com", "pw-12345-pw")
        TOTPDevice.objects.create(user=user, secret=two_factor.generate_secret(), confirmed=True)
        get.return_value = google_ok()
        data = self.client.post(self.url, {"id_token": "valid"}).json()
        self.assertTrue(data["two_factor_required"])
        self.assertNotIn("access", data)
