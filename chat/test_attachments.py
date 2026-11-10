from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.test import APIClient, APITestCase

from accounts.models import User
from chat.models import Conversation, Message
from listings.models import Category, Listing

# 1x1 transparent PNG
PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\rIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02\xfe\xa7\x9a\xa0\xa0\x00\x00\x00\x00IEND\xaeB`\x82"
)


@override_settings(MEDIA_ROOT="/tmp/choropia-test-media")
class ChatAttachmentTests(APITestCase):
    def setUp(self):
        self.buyer = User.objects.create_user("buyer@example.com", "pw-12345-pw")
        self.seller = User.objects.create_user("seller@example.com", "pw-12345-pw")
        self.outsider = User.objects.create_user("other@example.com", "pw-12345-pw")
        category = Category.objects.create(name="Phones")
        listing = Listing.objects.create(
            owner=self.seller, category=category, title="Phone", price="100.00", condition="used"
        )
        self.conversation = Conversation.objects.create(listing=listing, buyer=self.buyer, seller=self.seller)
        self.client = APIClient()
        self.client.force_authenticate(self.buyer)

    def _post(self, **fields):
        return self.client.post(
            "/api/v1/messages/", {"conversation": self.conversation.id, **fields}, format="multipart"
        )

    def test_text_message_still_works(self):
        response = self._post(body="hello")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["attachment_type"], "")
        self.assertIsNone(response.json()["attachment"])

    def test_image_attachment_without_text(self):
        response = self._post(attachment=SimpleUploadedFile("pic.png", PNG, content_type="image/png"))
        self.assertEqual(response.status_code, 201, response.content)
        data = response.json()
        self.assertEqual(data["attachment_type"], "image")
        self.assertTrue(data["attachment"])
        self.assertEqual(data["body"], "")

    def test_voice_note_keeps_duration(self):
        audio = SimpleUploadedFile("note.m4a", b"\x00" * 2048, content_type="audio/mp4")
        response = self._post(attachment=audio, duration_seconds="12")
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()["attachment_type"], "audio")
        self.assertEqual(response.json()["duration_seconds"], 12)

    def test_duration_is_ignored_for_non_audio(self):
        response = self._post(attachment=SimpleUploadedFile("pic.png", PNG), duration_seconds="9")
        self.assertEqual(response.status_code, 201)
        self.assertIsNone(response.json()["duration_seconds"])

    def test_empty_message_is_rejected(self):
        self.assertEqual(self._post(body="   ").status_code, 400)

    def test_unsupported_type_is_rejected(self):
        exe = SimpleUploadedFile("malware.exe", b"MZ", content_type="application/octet-stream")
        response = self._post(attachment=exe)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Message.objects.count(), 0)

    def test_oversized_attachment_is_rejected(self):
        big = SimpleUploadedFile("big.m4a", b"\x00" * (3 * 1024 * 1024 + 1), content_type="audio/mp4")
        self.assertEqual(self._post(attachment=big).status_code, 400)

    def test_overlong_voice_note_is_rejected(self):
        audio = SimpleUploadedFile("note.m4a", b"\x00" * 1024)
        self.assertEqual(self._post(attachment=audio, duration_seconds="601").status_code, 400)

    def test_non_participant_cannot_post(self):
        self.client.force_authenticate(self.outsider)
        response = self._post(body="sneaky")
        self.assertEqual(response.status_code, 403)

    def test_sender_can_delete_text_for_both_participants(self):
        message = Message.objects.create(conversation=self.conversation, sender=self.buyer, body="private note")

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.delete(f"/api/v1/messages/{message.id}/")

        self.assertEqual(response.status_code, 204)
        message.refresh_from_db()
        self.assertIsNotNone(message.deleted_at)
        self.assertEqual(message.body, "")

        for user in (self.buyer, self.seller):
            client = APIClient()
            client.force_authenticate(user)
            messages = client.get(f"/api/v1/messages/?conversation={self.conversation.id}").json()["results"]
            deleted = next(row for row in messages if row["id"] == message.id)
            self.assertTrue(deleted["is_deleted"])
            self.assertEqual(deleted["body"], "")

    def test_sender_can_delete_attachment_and_storage_file(self):
        response = self._post(attachment=SimpleUploadedFile("pic.png", PNG, content_type="image/png"))
        message_id = response.json()["id"]
        message = Message.objects.get(pk=message_id)
        attachment_name = message.attachment.name
        storage = message.attachment.storage
        self.assertTrue(storage.exists(attachment_name))

        with self.captureOnCommitCallbacks(execute=True):
            delete_response = self.client.delete(f"/api/v1/messages/{message_id}/")

        self.assertEqual(delete_response.status_code, 204)
        message.refresh_from_db()
        self.assertFalse(message.attachment)
        self.assertFalse(storage.exists(attachment_name))

    def test_only_sender_can_delete_message(self):
        message = Message.objects.create(conversation=self.conversation, sender=self.buyer, body="private note")
        self.client.force_authenticate(self.seller)

        self.assertEqual(self.client.delete(f"/api/v1/messages/{message.id}/").status_code, 403)
        message.refresh_from_db()
        self.assertIsNone(message.deleted_at)

        self.client.force_authenticate(self.outsider)
        self.assertEqual(self.client.delete(f"/api/v1/messages/{message.id}/").status_code, 404)

    def test_offer_and_listing_reference_messages_cannot_be_deleted(self):
        for message_type in (Message.MessageType.OFFER, Message.MessageType.LISTING_REF):
            message = Message.objects.create(
                conversation=self.conversation, sender=self.buyer, message_type=message_type
            )
            response = self.client.delete(f"/api/v1/messages/{message.id}/")
            self.assertEqual(response.status_code, 400)
            message.refresh_from_db()
            self.assertIsNone(message.deleted_at)
