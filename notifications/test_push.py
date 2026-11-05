from unittest import mock

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from accounts.models import User
from listings.models import Category, Listing
from notifications import push
from notifications.models import DeviceToken, Notification
from notifications.services import create_notification
from social.models import Follow

FAKE_ACCOUNT = '{"project_id": "demo", "client_email": "x@demo.iam", "private_key": "unused"}'


class DeviceRegistrationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("phone@example.com", "pw12345!")
        self.other = User.objects.create_user("other@example.com", "pw12345!")
        self.client = APIClient()

    def test_register_move_and_remove_a_token(self):
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.post("/api/v1/notifications/devices/", {"token": "abc"}).status_code, 204)
        self.assertEqual(DeviceToken.objects.get(token="abc").user, self.user)
        self.client.force_authenticate(self.other)  # same phone, different account signs in
        self.client.post("/api/v1/notifications/devices/", {"token": "abc"})
        self.assertEqual(DeviceToken.objects.get(token="abc").user, self.other)
        self.assertEqual(self.client.delete("/api/v1/notifications/devices/", {"token": "abc"}).status_code, 204)
        self.assertFalse(DeviceToken.objects.exists())

    def test_needs_login_and_a_token(self):
        self.assertEqual(APIClient().post("/api/v1/notifications/devices/", {"token": "abc"}).status_code, 401)
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.post("/api/v1/notifications/devices/", {}).status_code, 400)


class PushSendingTests(TestCase):
    def setUp(self):
        self.recipient = User.objects.create_user("r@example.com", "pw12345!")
        self.actor = User.objects.create_user("a@example.com", "pw12345!", first_name="Ada")
        DeviceToken.objects.create(user=self.recipient, token="tok1")

    def test_does_nothing_until_firebase_is_configured(self):
        with mock.patch("notifications.push.requests.post") as post:
            with self.captureOnCommitCallbacks(execute=True):
                create_notification(self.recipient, Notification.Type.MESSAGE, "New message", actor=self.actor)
        post.assert_not_called()

    @override_settings(FIREBASE_SERVICE_ACCOUNT_JSON=FAKE_ACCOUNT)
    def test_sends_a_data_message_to_each_device_when_configured(self):
        ok = mock.Mock(ok=True, status_code=200)
        with mock.patch("notifications.push._access_token", return_value="t"), mock.patch(
            "notifications.push.requests.post", return_value=ok
        ) as post:
            with self.captureOnCommitCallbacks(execute=True):
                create_notification(self.recipient, Notification.Type.MESSAGE, "New message from Ada", actor=self.actor)
        self.assertEqual(post.call_count, 1)
        message = post.call_args.kwargs["json"]["message"]
        self.assertEqual(message["token"], "tok1")
        self.assertEqual(message["data"]["body"], "New message from Ada")
        self.assertEqual(message["data"]["type"], "message")

    @override_settings(FIREBASE_SERVICE_ACCOUNT_JSON=FAKE_ACCOUNT)
    def test_dead_tokens_are_removed_and_failures_never_raise(self):
        gone = mock.Mock(ok=False, status_code=404, text="UNREGISTERED")
        with mock.patch("notifications.push._access_token", return_value="t"), mock.patch(
            "notifications.push.requests.post", return_value=gone
        ):
            with self.captureOnCommitCallbacks(execute=True):
                create_notification(self.recipient, Notification.Type.MESSAGE, "hi", actor=self.actor)
        self.assertFalse(DeviceToken.objects.exists())
        with mock.patch("notifications.push._access_token", side_effect=RuntimeError("boom")):
            DeviceToken.objects.create(user=self.recipient, token="tok2")
            with self.captureOnCommitCallbacks(execute=True):
                create_notification(self.recipient, Notification.Type.MESSAGE, "hi again", actor=self.actor)


class NewListingNotificationTests(TestCase):
    def test_followers_hear_about_a_new_listing(self):
        seller = User.objects.create_user("s@example.com", "pw12345!", first_name="Sam")
        fan = User.objects.create_user("f@example.com", "pw12345!")
        User.objects.create_user("stranger@example.com", "pw12345!")
        Follow.objects.create(follower=fan, content_type=ContentType.objects.get_for_model(User), object_id=seller.pk)
        category = Category.objects.create(name="Gadgets")
        listing = Listing.objects.create(owner=seller, category=category, title="Phone", price="10.00", condition="new")
        note = Notification.objects.get(recipient=fan)
        self.assertEqual(note.notification_type, "new_listing")
        self.assertIn("Phone", note.verb)
        self.assertEqual(note.target_object_id, listing.pk)
        self.assertEqual(Notification.objects.filter(notification_type="new_listing").count(), 1)  # only the follower, not the stranger
