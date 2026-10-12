from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient, APITestCase

from reels.models import Reel

User = get_user_model()


def tiny_mp4():
    # A fresh file per call — SimpleUploadedFile's underlying buffer is consumed on upload, so
    # one shared instance can't be reused across multiple requests/tests.
    return SimpleUploadedFile("clip.mp4", b"\x00\x00\x00\x18ftypmp42", content_type="video/mp4")


class ReelApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="creator@example.com", password="pw12345!")
        self.other = User.objects.create_user(email="viewer@example.com", password="pw12345!")
        self.client = APIClient()

    def test_create_reel_requires_auth(self):
        response = self.client.post("/api/v1/reels/", {"video": tiny_mp4(), "caption": "hi"}, format="multipart")
        self.assertEqual(response.status_code, 401)

    def test_create_and_list_reel(self):
        self.client.force_authenticate(self.user)
        response = self.client.post("/api/v1/reels/", {"video": tiny_mp4(), "caption": "First reel"}, format="multipart")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["creator_id"], self.user.id)
        self.assertEqual(response.data["likes_count"], 0)

        self.client.force_authenticate(None)
        response = self.client.get("/api/v1/reels/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)

    def test_like_unlike_cycle(self):
        reel = Reel.objects.create(owner=self.user, video=tiny_mp4(), caption="x")
        self.client.force_authenticate(self.other)

        response = self.client.post("/api/v1/reel-likes/", {"reel": reel.id})
        self.assertEqual(response.status_code, 201, response.data)
        like_id = response.data["id"]

        response = self.client.get(f"/api/v1/reels/{reel.id}/")
        self.assertTrue(response.data["is_liked"])
        self.assertEqual(response.data["likes_count"], 1)

        response = self.client.delete(f"/api/v1/reel-likes/{like_id}/")
        self.assertEqual(response.status_code, 204)

        response = self.client.get(f"/api/v1/reels/{reel.id}/")
        self.assertFalse(response.data["is_liked"])

    def test_cannot_like_twice(self):
        reel = Reel.objects.create(owner=self.user, video=tiny_mp4())
        self.client.force_authenticate(self.other)
        self.client.post("/api/v1/reel-likes/", {"reel": reel.id})
        response = self.client.post("/api/v1/reel-likes/", {"reel": reel.id})
        self.assertEqual(response.status_code, 400)

    def test_only_owner_can_delete_reel(self):
        reel = Reel.objects.create(owner=self.user, video=tiny_mp4())
        self.client.force_authenticate(self.other)
        response = self.client.delete(f"/api/v1/reels/{reel.id}/")
        self.assertEqual(response.status_code, 403)

    def test_comment_on_reel(self):
        reel = Reel.objects.create(owner=self.user, video=tiny_mp4())
        self.client.force_authenticate(self.other)
        response = self.client.post("/api/v1/reel-comments/", {"reel": reel.id, "body": "Nice!"})
        self.assertEqual(response.status_code, 201, response.data)

        response = self.client.get(f"/api/v1/reel-comments/?reel={reel.id}")
        self.assertEqual(response.data["count"], 1)
