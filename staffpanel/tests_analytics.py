from django.test import TestCase

from accounts.models import User
from staffpanel.models import PageView

UA = {"HTTP_USER_AGENT": "Mozilla/5.0 (iPhone) Safari"}


class AnalyticsTests(TestCase):
    def test_a_visit_is_counted_without_storing_an_ip(self):
        r = self.client.post("/api/v1/analytics/hit/", {"path": "/feed?x=1", "vid": "abcdef123456", "ref": "https://www.google.com/search", "w": 390}, content_type="application/json", **UA)
        self.assertEqual(r.status_code, 204)
        view = PageView.objects.get()
        self.assertEqual((view.path, view.referrer, view.device), ("/feed", "google.com", "phone"))

    def test_bots_staff_pages_and_bad_ids_are_ignored(self):
        post = lambda body, ua="Mozilla/5.0": self.client.post("/api/v1/analytics/hit/", body, content_type="application/json", HTTP_USER_AGENT=ua)  # noqa: E731
        post({"path": "/feed", "vid": "abcdef123456"}, "Googlebot/2.1")
        post({"path": "/staff/inbox/", "vid": "abcdef123456"})
        post({"path": "/feed", "vid": "x"})
        self.assertEqual(PageView.objects.count(), 0)

    def test_the_analytics_page_shows_the_numbers_to_staff_only(self):
        for vid, path in (("visitorone111", "/feed"), ("visitorone111", "/marketplace"), ("visitortwo222", "/feed")):
            self.client.post("/api/v1/analytics/hit/", {"path": path, "vid": vid, "w": 1280}, content_type="application/json", **UA)
        self.client.logout()
        self.assertNotEqual(self.client.get("/staff/analytics/").status_code, 200)
        boss = User.objects.create_superuser("boss@example.com", "pw12345!")
        self.client.force_login(boss)
        for days in (7, 30, 90):
            page = self.client.get(f"/staff/analytics/?days={days}")
            self.assertEqual(page.status_code, 200)
        self.assertContains(page, "/feed")
        self.assertContains(page, "<svg")
