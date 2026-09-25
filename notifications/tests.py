from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from notifications.models import Notification
from notifications.services import create_notification

User = get_user_model()


class RealtimePushIsBestEffortTests(TestCase):
    def test_notification_is_saved_even_if_the_channel_layer_is_down(self):
        recipient = User.objects.create_user(email="r@example.com", password="pw12345!")
        actor = User.objects.create_user(email="a@example.com", password="pw12345!")

        broken_layer = mock.Mock()
        broken_layer.group_send = mock.AsyncMock(side_effect=ConnectionError("redis unreachable"))
        with mock.patch("notifications.services.get_channel_layer", return_value=broken_layer):
            notification = create_notification(
                recipient, Notification.Type.FOLLOW, "started following you", actor=actor
            )

        self.assertIsNotNone(notification)
        self.assertTrue(Notification.objects.filter(pk=notification.pk).exists())
