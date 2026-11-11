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
        page = self.client.get("/staff/inbox/")
        self.assertContains(page, "Send reply")
