from rest_framework.test import APIClient, APITestCase

from accounts.models import User
from listings.models import Category, Listing
from social.models import Comment, GuestLike, Like
from social.guest_likes import guest_id_from_token


class CommentApiTests(APITestCase):
    def setUp(self):
        self.author = User.objects.create_user(
            "commenter@example.com",
            "pw-12345-pw",
            first_name="Ada",
            last_name="Okon",
        )
        self.category = Category.objects.create(name="Books")
        self.listing = Listing.objects.create(
            owner=self.author,
            category=self.category,
            title="Book",
            price="100.00",
        )

    def test_comment_payload_has_public_author_identity(self):
        client = APIClient()
        client.force_authenticate(self.author)
        response = client.post(
            "/api/v1/comments/",
            {"listing": self.listing.pk, "body": "Good condition"},
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(
            response.json()["author"],
            {
                "id": self.author.pk,
                "display_name": "Ada Okon",
                "username": f"user-{self.author.pk}",
                "avatar_url": None,
                "verified": False,
            },
        )

    def test_guest_comment_returns_auth_required_code(self):
        response = APIClient().post(
            "/api/v1/comments/",
            {"listing": self.listing.pk, "body": "Good condition"},
            format="json",
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["code"], "AUTH_REQUIRED")
        self.assertFalse(Comment.objects.exists())


class GuestListingLikeApiTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user("seller@example.com", "pw-12345-pw")
        self.category = Category.objects.create(name="Books")
        self.listing = Listing.objects.create(
            owner=self.owner,
            category=self.category,
            title="Book",
            price="100.00",
        )

    def get_guest_token(self):
        response = self.client.post("/api/v1/likes/guest-token/", {}, format="json")
        self.assertEqual(response.status_code, 200, response.content)
        token = response.json()["token"]
        self.assertIsNotNone(guest_id_from_token(token))
        return token

    def test_guest_like_is_signed_idempotent_and_visible_in_listing_payload(self):
        token = self.get_guest_token()
        headers = {"HTTP_X_GUEST_LIKE_TOKEN": token}

        first = self.client.post(
            "/api/v1/likes/guest/",
            {"listing": self.listing.pk},
            format="json",
            **headers,
        )
        second = self.client.post(
            "/api/v1/likes/guest/",
            {"listing": self.listing.pk},
            format="json",
            **headers,
        )

        self.assertEqual(first.status_code, 200, first.content)
        self.assertEqual(second.status_code, 200, second.content)
        self.assertEqual(GuestLike.objects.count(), 1)

        listing = self.client.get(
            f"/api/v1/listings/{self.listing.pk}/",
            **headers,
        )
        self.assertEqual(listing.status_code, 200, listing.content)
        self.assertEqual(listing.json()["likes_count"], 1)
        self.assertTrue(listing.json()["is_liked"])

    def test_guest_unlike_is_idempotent_and_bad_token_is_rejected(self):
        token = self.get_guest_token()
        headers = {"HTTP_X_GUEST_LIKE_TOKEN": token}
        self.client.post(
            "/api/v1/likes/guest/",
            {"listing": self.listing.pk},
            format="json",
            **headers,
        )

        first = self.client.delete(
            "/api/v1/likes/guest/",
            {"listing": self.listing.pk},
            format="json",
            **headers,
        )
        second = self.client.delete(
            "/api/v1/likes/guest/",
            {"listing": self.listing.pk},
            format="json",
            **headers,
        )
        invalid = self.client.post(
            "/api/v1/likes/guest/",
            {"listing": self.listing.pk},
            format="json",
            HTTP_X_GUEST_LIKE_TOKEN="not-a-signed-token",
        )

        self.assertEqual(first.status_code, 200, first.content)
        self.assertEqual(second.status_code, 200, second.content)
        self.assertFalse(GuestLike.objects.exists())
        self.assertEqual(invalid.status_code, 400)
        self.assertFalse(GuestLike.objects.exists())

    def test_authenticated_likes_keep_the_existing_endpoint_and_guest_api_is_separate(self):
        user = User.objects.create_user("buyer@example.com", "pw-12345-pw")
        guest_token = self.get_guest_token()
        self.client.force_authenticate(user)

        response = self.client.post(
            "/api/v1/likes/",
            {"listing": self.listing.pk},
            format="json",
        )
        guest_route = self.client.post(
            "/api/v1/likes/guest/",
            {"listing": self.listing.pk},
            format="json",
            HTTP_X_GUEST_LIKE_TOKEN=guest_token,
        )

        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(Like.objects.count(), 1)
        self.assertEqual(guest_route.status_code, 400)
        self.assertFalse(GuestLike.objects.exists())
