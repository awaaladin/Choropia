from django.core import mail
from django.test import TestCase

from accounts.models import User
from merchants.models import Merchant, MerchantApplication


class StorefrontDecisionTests(TestCase):
    def setUp(self):
        self.boss = User.objects.create_superuser("boss@example.com", "pw12345!")
        self.client.force_login(self.boss)
        self.owner = User.objects.create_user("shop@example.com", "pw12345!", first_name="Shola")
        self.app = MerchantApplication.objects.create(applicant=self.owner, business_name="Shola Gadgets", business_phone="0801", business_address="Uyo")

    def test_inbox_lists_the_application_with_buttons(self):
        page = self.client.get("/staff/inbox/")
        self.assertContains(page, "Shola Gadgets")
        self.assertContains(page, "Approve")

    def test_approving_opens_the_storefront_verifies_the_seller_and_emails_them(self):
        mail.outbox.clear()
        self.client.post(f"/staff/inbox/storefronts/{self.app.pk}/decide/", {"decision": "approve"})
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, "approved")
        self.assertTrue(Merchant.objects.filter(user=self.owner).exists())
        self.owner.profile.refresh_from_db()
        self.assertTrue(self.owner.profile.seller_verified)
        self.assertTrue(any("shop@example.com" in m.to and "approved" in m.subject for m in mail.outbox))

    def test_rejecting_records_the_reason_and_tells_them(self):
        mail.outbox.clear()
        self.client.post(f"/staff/inbox/storefronts/{self.app.pk}/decide/", {"decision": "reject", "reason": "Please add a clear address."})
        self.app.refresh_from_db()
        self.assertEqual((self.app.status, self.app.rejection_reason), ("rejected", "Please add a clear address."))
        self.assertFalse(Merchant.objects.filter(user=self.owner).exists())
        self.assertTrue(any("shop@example.com" in m.to and "Please add a clear address." in m.body for m in mail.outbox))

    def test_you_can_change_your_mind_both_ways_and_it_is_all_kept(self):
        d = f"/staff/inbox/storefronts/{self.app.pk}/decide/"
        self.client.post(d, {"decision": "reject", "reason": "Not sure yet."})
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, "rejected")
        # rejected -> approve instead
        self.client.post(d, {"decision": "approve"})
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, "approved")
        self.assertEqual(Merchant.objects.get(user=self.owner).status, "active")
        self.owner.profile.refresh_from_db()
        self.assertTrue(self.owner.profile.seller_verified)
        # approved -> withdraw: suspended and the badge goes
        mail.outbox.clear()
        self.client.post(d, {"decision": "reject", "reason": "Documents did not check out."})
        self.app.refresh_from_db()
        self.owner.profile.refresh_from_db()
        self.assertEqual(self.app.status, "rejected")
        self.assertEqual(Merchant.objects.get(user=self.owner).status, "suspended")
        self.assertFalse(self.owner.profile.seller_verified)
        self.assertTrue(any("withdrawn" in m.body for m in mail.outbox))
        # and approve once more: the storefront comes back
        self.client.post(d, {"decision": "approve"})
        self.assertEqual(Merchant.objects.get(user=self.owner).status, "active")

    def test_decided_tab_keeps_the_history_with_change_buttons(self):
        self.client.post(f"/staff/inbox/storefronts/{self.app.pk}/decide/", {"decision": "approve"})
        page = self.client.get("/staff/inbox/?tab=decided")
        self.assertContains(page, "Shola Gadgets")
        self.assertContains(page, "withdraw approval")
        self.assertNotContains(self.client.get("/staff/inbox/"), "Shola Gadgets")
