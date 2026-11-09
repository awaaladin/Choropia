from cryptography.fernet import Fernet
from django.core.management import call_command
from django.core.exceptions import ImproperlyConfigured
from django.db import connection, transaction
from django.db.models import Q
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from chat.models import Conversation, Message
from listings.models import Category, Listing


class DirectThreadTests(TestCase):
    def setUp(self):
        self.buyer = User.objects.create_user("buyer@example.com", "pw-12345-pw")
        self.seller = User.objects.create_user("seller@example.com", "pw-12345-pw")
        self.category = Category.objects.create(name="Phones")
        self.listing_a = Listing.objects.create(owner=self.seller, category=self.category, title="Alpha", price="100.00")
        self.listing_b = Listing.objects.create(owner=self.seller, category=self.category, title="Bravo", price="200.00")

    def test_pair_thread_reuses_existing_conversation_regardless_of_listing(self):
        conversation_a, created_a = Conversation.get_or_create_direct_thread(self.buyer, self.seller, listing=self.listing_a)
        conversation_b, created_b = Conversation.get_or_create_direct_thread(self.buyer, self.seller, listing=self.listing_b)

        self.assertTrue(created_a)
        self.assertFalse(created_b)
        self.assertEqual(conversation_a.pk, conversation_b.pk)
        self.assertEqual(
            Conversation.objects.filter(Q(buyer=self.buyer, seller=self.seller) | Q(buyer=self.seller, seller=self.buyer)).count(),
            1,
        )

    def test_conversation_open_endpoint_returns_existing_thread(self):
        client = APIClient()
        client.force_authenticate(self.buyer)

        first = client.post("/api/v1/conversations/open/", {"other_user_id": self.seller.id, "listing_id": self.listing_a.id}, format="json")
        second = client.post("/api/v1/conversations/open/", {"other_user_id": self.seller.id, "listing_id": self.listing_b.id}, format="json")

        self.assertIn(first.status_code, (200, 201), first.content)
        self.assertEqual(second.status_code, 200, second.content)
        self.assertEqual(first.json()["id"], second.json()["id"])
        self.assertEqual(Conversation.objects.count(), 1)

    def test_listing_reference_is_added_once_for_repeated_open_within_six_hours(self):
        client = APIClient()
        client.force_authenticate(self.buyer)

        first = client.post(
            "/api/v1/conversations/open/",
            {"other_user_id": self.seller.id, "listing_id": self.listing_a.id},
            format="json",
        )
        second = client.post(
            "/api/v1/conversations/open/",
            {"other_user_id": self.seller.id, "listing_id": self.listing_a.id},
            format="json",
        )

        self.assertIn(first.status_code, (200, 201), first.content)
        self.assertEqual(second.status_code, 200, second.content)
        reference = Message.objects.get(message_type=Message.MessageType.LISTING_REF)
        self.assertEqual(reference.referenced_listing_id, self.listing_a.id)
        self.assertEqual(reference.listing_snapshot["title"], "Alpha")
        self.assertEqual(reference.listing_snapshot["price_kobo"], 10_000)

    def test_open_without_listing_creates_direct_thread(self):
        client = APIClient()
        client.force_authenticate(self.buyer)

        response = client.post(
            "/api/v1/conversations/open/",
            {"other_user_id": self.seller.id},
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.content)
        self.assertIsNone(response.json()["listing"])
        self.assertFalse(Message.objects.exists())

    def test_message_body_is_encrypted_in_database_and_decrypted_for_api(self):
        conversation, _ = Conversation.get_or_create_direct_thread(self.buyer, self.seller)
        message = Message.objects.create(conversation=conversation, sender=self.buyer, body="private message")

        with connection.cursor() as cursor:
            cursor.execute(
                f"SELECT body FROM {connection.ops.quote_name(Message._meta.db_table)} WHERE id = %s",
                [message.pk],
            )
            stored_body = cursor.fetchone()[0]

        self.assertNotIn("private message", stored_body)
        self.assertTrue(stored_body.startswith("fernet:v1:"))
        message.refresh_from_db()
        self.assertEqual(message.body, "private message")

    def test_legacy_plaintext_is_readable_until_migration_runs(self):
        conversation, _ = Conversation.get_or_create_direct_thread(self.buyer, self.seller)
        message = Message.objects.create(conversation=conversation, sender=self.buyer, body="legacy message")
        with connection.cursor() as cursor:
            cursor.execute(
                f"UPDATE {connection.ops.quote_name(Message._meta.db_table)} SET body = %s WHERE id = %s",
                ["legacy message", message.pk],
            )

        message.refresh_from_db()
        self.assertEqual(message.body, "legacy message")

    @override_settings(CHAT_MESSAGE_ENCRYPTION_KEYS="")
    def test_sending_a_message_without_a_key_fails_instead_of_storing_plaintext(self):
        conversation, _ = Conversation.get_or_create_direct_thread(self.buyer, self.seller)

        with transaction.atomic():
            with self.assertRaises(ImproperlyConfigured):
                Message.objects.create(
                    conversation=conversation, sender=self.buyer, body="must not be plaintext"
                )

        self.assertFalse(Message.objects.exists())

    def test_key_rotation_reencrypts_messages_with_the_new_primary_key(self):
        conversation, _ = Conversation.get_or_create_direct_thread(self.buyer, self.seller)
        old_key = Fernet.generate_key().decode("ascii")
        new_key = Fernet.generate_key().decode("ascii")
        with override_settings(CHAT_MESSAGE_ENCRYPTION_KEYS=old_key):
            message = Message.objects.create(conversation=conversation, sender=self.buyer, body="rotate me")

        with connection.cursor() as cursor:
            cursor.execute(
                f"SELECT body FROM {connection.ops.quote_name(Message._meta.db_table)} WHERE id = %s",
                [message.pk],
            )
            old_ciphertext = cursor.fetchone()[0]

        with override_settings(CHAT_MESSAGE_ENCRYPTION_KEYS=f"{new_key},{old_key}"):
            call_command("rotate_chat_message_keys", "--apply", verbosity=0)
            with connection.cursor() as cursor:
                cursor.execute(
                    f"SELECT body FROM {connection.ops.quote_name(Message._meta.db_table)} WHERE id = %s",
                    [message.pk],
                )
                new_ciphertext = cursor.fetchone()[0]

        self.assertNotEqual(old_ciphertext, new_ciphertext)
        with override_settings(CHAT_MESSAGE_ENCRYPTION_KEYS=new_key):
            message.refresh_from_db()
            self.assertEqual(message.body, "rotate me")

    def test_additional_key_decrypts_messages_without_changing_primary_encryption_key(self):
        conversation, _ = Conversation.get_or_create_direct_thread(self.buyer, self.seller)
        primary_key = Fernet.generate_key().decode("ascii")
        additional_key = Fernet.generate_key().decode("ascii")
        with override_settings(CHAT_MESSAGE_ENCRYPTION_KEYS=additional_key):
            message = Message.objects.create(conversation=conversation, sender=self.buyer, body="secondary key")

        with override_settings(
            CHAT_MESSAGE_ENCRYPTION_KEYS=primary_key,
            CHAT_MESSAGE_ENCRYPTION_KEYS_ADDITIONAL=additional_key,
        ):
            message.refresh_from_db()
            self.assertEqual(message.body, "secondary key")
            primary_message = Message.objects.create(
                conversation=conversation, sender=self.buyer, body="primary key"
            )

        with connection.cursor() as cursor:
            cursor.execute(
                f"SELECT body FROM {connection.ops.quote_name(Message._meta.db_table)} WHERE id = %s",
                [primary_message.pk],
            )
            primary_ciphertext = cursor.fetchone()[0]
        self.assertEqual(
            Fernet(primary_key.encode("ascii")).decrypt(primary_ciphertext[len("fernet:v1:") :].encode("ascii")),
            b"primary key",
        )
