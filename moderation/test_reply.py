from unittest import mock

from django.core import mail
from django.test import TestCase

from accounts.models import User
from moderation.models import ContactMessage


class ContactReplyTests(TestCase):
    def setUp(self):
        self.boss = User.objects.create_superuser("boss@example.com", "pw12345!", first_name="Boss")
        self.client.force_login(self.boss)
        self.msg = ContactMessage.objects.create(name="Ada Obi", email="ada@example.com", topic="question", message="Are you in Aba?")

    def test_reply_is_emailed_to_the_sender_and_recorded(self):
        mail.outbox.clear()
        r = self.client.post(f"/staff/inbox/contact/{self.msg.pk}/reply/", {"reply": "Not yet, we start in Uyo."})
        self.assertEqual(r.status_code, 302)
        self.msg.refresh_from_db()
        self.assertTrue(self.msg.handled)
        self.assertEqual(self.msg.reply, "Not yet, we start in Uyo.")
        self.assertEqual(self.msg.replied_by, self.boss)
        self.assertIsNotNone(self.msg.replied_at)
        sent = [m for m in mail.outbox if "ada@example.com" in m.to]
        self.assertEqual(len(sent), 1)
        self.assertIn("Not yet, we start in Uyo.", sent[0].body)
        self.assertIn("Are you in Aba?", sent[0].body)

    def test_a_failed_send_is_not_marked_as_answered(self):
        with mock.patch("staffpanel.views.emails.send_email", return_value=False):
            self.client.post(f"/staff/inbox/contact/{self.msg.pk}/reply/", {"reply": "Hello"})
        self.msg.refresh_from_db()
        self.assertFalse(self.msg.handled)
        self.assertEqual(self.msg.reply, "")

    def test_empty_reply_is_refused_and_the_inbox_shows_the_box(self):
        self.client.post(f"/staff/inbox/contact/{self.msg.pk}/reply/", {"reply": "  "})
        self.msg.refresh_from_db()
        self.assertFalse(self.msg.handled)
        page = self.client.get(f"/staff/inbox/contact/{self.msg.pk}/")
        self.assertContains(page, "Send reply")

    def test_a_replied_message_can_be_reopened_and_keeps_its_history(self):
        self.client.post(f"/staff/inbox/contact/{self.msg.pk}/reply/", {"reply": "Not yet."})
        self.client.post(f"/staff/inbox/contact/{self.msg.pk}/reopen/")
        self.msg.refresh_from_db()
        self.assertFalse(self.msg.handled)
        self.assertEqual(self.msg.reply, "Not yet.")
        self.assertContains(self.client.get("/staff/inbox/"), "Are you in Aba?")
        self.assertEqual(self.msg.replies.count(), 1)

    def test_a_report_decision_can_be_changed_back_to_waiting(self):
        from django.contrib.contenttypes.models import ContentType

        from listings.models import Category, Listing
        from moderation.models import Report

        seller = User.objects.create_user("s@example.com", "pw12345!")
        listing = Listing.objects.create(owner=seller, category=Category.objects.create(name="Gadgets"), title="Phone", price="5.00")
        report = Report.objects.create(reporter=seller, content_type=ContentType.objects.get_for_model(Listing), object_id=listing.pk, reason="Scam")
        self.client.post(f"/staff/inbox/reports/{report.pk}/resolve/", {"decision": "dismissed"})
        report.refresh_from_db()
        self.assertEqual(report.status, "dismissed")
        self.client.post(f"/staff/inbox/reports/{report.pk}/resolve/", {"decision": "pending"})
        report.refresh_from_db()
        self.assertEqual((report.status, report.reviewed_by), ("pending", None))

    def test_the_conversation_page_shows_the_whole_thread_and_keeps_every_reply(self):
        self.client.post(f"/staff/inbox/contact/{self.msg.pk}/reply/", {"reply": "First answer."})
        self.client.post(f"/staff/inbox/contact/{self.msg.pk}/reply/", {"reply": "Second answer."})
        page = self.client.get(f"/staff/inbox/contact/{self.msg.pk}/")
        self.assertContains(page, "Are you in Aba?")
        self.assertContains(page, "First answer.")
        self.assertContains(page, "Second answer.")
        self.assertEqual(self.msg.replies.count(), 2)

    def test_inbox_rows_link_to_the_conversation(self):
        self.assertContains(self.client.get("/staff/inbox/"), f"/staff/inbox/contact/{self.msg.pk}/")
