from django.contrib.contenttypes.models import ContentType
from django.core import mail
from django.test import TestCase

from accounts.models import User
from listings.models import Category, Listing
from merchants.models import MerchantApplication
from moderation.models import ContactMessage, Report
from staffpanel.models import AuditLog


class PreviewAndCongratulationsTests(TestCase):
    def setUp(self):
        self.boss = User.objects.create_superuser("boss@example.com", "pw12345!")
        self.client.force_login(self.boss)
        self.owner = User.objects.create_user("shop@example.com", "pw12345!", first_name="Shola")
        self.app = MerchantApplication.objects.create(applicant=self.owner, business_name="Shola Gadgets", business_phone="0801", business_address="Uyo", business_description="Phones")

    def test_activity_log_rows_link_to_the_item(self):
        AuditLog.objects.create(staff=self.boss, action="storefront.approve", target=f"application {self.app.pk}")
        AuditLog.objects.create(staff=self.boss, action="contact.replied", target="message 7")
        AuditLog.objects.create(staff=self.boss, action="keys.recovered")
        page = self.client.get("/staff/audit/")
        self.assertContains(page, f'href="/staff/inbox/storefronts/{self.app.pk}/"')
        self.assertContains(page, 'href="/staff/inbox/contact/7/"')

    def test_storefront_and_report_pages_preview_the_item(self):
        page = self.client.get(f"/staff/inbox/storefronts/{self.app.pk}/")
        self.assertContains(page, "Shola Gadgets")
        self.assertContains(page, "Phones")
        self.assertContains(page, "Approve and verify")
        listing = Listing.objects.create(owner=self.owner, category=Category.objects.create(name="G"), title="Fake phone", price="5.00")
        report = Report.objects.create(reporter=self.boss, content_type=ContentType.objects.get_for_model(Listing), object_id=listing.pk, reason="Scam")
        page = self.client.get(f"/staff/inbox/reports/{report.pk}/")
        self.assertContains(page, "Fake phone")
        self.assertContains(page, "Scam")

    def test_approving_a_storefront_sends_the_congratulations_with_the_badge(self):
        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(f"/staff/inbox/storefronts/{self.app.pk}/decide/", {"decision": "approve"})
        sent = [m for m in mail.outbox if "shop@example.com" in m.to]
        self.assertEqual(len(sent), 1)
        self.assertIn("Congratulations", sent[0].subject)
        html = sent[0].alternatives[0][0]
        self.assertIn("verified-badge.png", html)
        self.assertIn("Shola Gadgets", html)
        self.owner.profile.refresh_from_db()
        self.assertTrue(self.owner.profile.seller_verified)

    def test_approving_through_the_api_also_congratulates(self):
        from rest_framework.test import APIClient

        api = APIClient()
        api.force_authenticate(self.boss)
        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            r = api.post(f"/api/v1/merchant-applications/{self.app.pk}/review/", {"action": "approve"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(any("Congratulations" in m.subject and "shop@example.com" in m.to for m in mail.outbox))

    def test_verifying_a_seller_by_hand_congratulates_too(self):
        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(f"/staff/people/{self.owner.pk}/verify-seller/")
        self.assertTrue(any("verified Choropia seller" in m.subject and "shop@example.com" in m.to for m in mail.outbox))
