"""Regression tests for the two production 500s found on the live site (16 Oct):
  1. uploading a photo when file storage is read-only/unavailable;
  2. password reset when the SMTP server can't be reached.
"""
import errno
import io
import smtplib
from unittest import mock

import requests
from botocore.exceptions import ClientError
from PIL import Image
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient, APITestCase

from accounts.models import User
from common.exceptions import is_storage_failure
from listings.models import Category, Listing, ListingPhoto

def real_png():
    """A genuinely valid image (the serializer verifies uploads with Pillow)."""
    buffer = io.BytesIO()
    Image.new("RGB", (4, 4), "white").save(buffer, format="PNG")
    return buffer.getvalue()


class StorageClassificationTests(APITestCase):
    def test_read_only_filesystem_is_a_storage_failure(self):
        self.assertTrue(is_storage_failure(OSError(errno.EROFS, "Read-only file system")))

    def test_bucket_errors_are_storage_failures(self):
        error = ClientError({"Error": {"Code": "AccessDenied", "Message": "no"}}, "PutObject")
        self.assertTrue(is_storage_failure(error))

    def test_network_errors_are_not_mistaken_for_storage(self):
        # requests' exceptions subclass OSError; a failed Gaxtron call must not read as "uploads down".
        self.assertFalse(is_storage_failure(requests.ConnectionError("refused")))
        self.assertFalse(is_storage_failure(OSError(errno.ECONNREFUSED, "refused")))
        self.assertFalse(is_storage_failure(ValueError("boom")))


class ListingUploadOutageTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.user = User.objects.create_user("seller@example.com", "pw-12345-pw")
        self.category = Category.objects.create(name="Phones")
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def _post(self, with_photo):
        data = {"title": "Phone", "description": "d", "price": "100.00", "condition": "used", "category": self.category.id}
        if with_photo:
            data["uploaded_photos"] = SimpleUploadedFile("p.png", real_png(), content_type="image/png")
        return self.client.post("/api/v1/listings/", data, format="multipart")

    def test_photo_upload_during_storage_outage_is_503_and_leaves_no_listing(self):
        outage = OSError(errno.EROFS, "Read-only file system: '/var/task/mediafiles'")
        with mock.patch("django.core.files.storage.FileSystemStorage._save", side_effect=outage):
            response = self._post(with_photo=True)
        self.assertEqual(response.status_code, 503)
        self.assertIn("temporarily unavailable", response.json()["detail"])
        # The production bug left a photo-less listing behind; it must be rolled back now.
        self.assertEqual(Listing.objects.count(), 0)
        self.assertEqual(ListingPhoto.objects.count(), 0)

    def test_listing_without_photos_still_works_during_outage(self):
        outage = OSError(errno.EROFS, "Read-only file system")
        with mock.patch("django.core.files.storage.FileSystemStorage._save", side_effect=outage):
            response = self._post(with_photo=False)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Listing.objects.count(), 1)


class PasswordResetMailOutageTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        User.objects.create_user("known@example.com", "pw-12345-pw")

    def test_smtp_failure_still_answers_200_and_does_not_leak_existence(self):
        broken = smtplib.SMTPServerDisconnected("please run connect() first")
        with mock.patch("accounts.views.send_mail", side_effect=broken):
            known = self.client.post("/api/v1/auth/password-reset/", {"email": "known@example.com"})
            unknown = self.client.post("/api/v1/auth/password-reset/", {"email": "nobody@example.com"})
        self.assertEqual(known.status_code, 200)
        self.assertEqual(unknown.status_code, 200)
        self.assertEqual(known.json(), unknown.json())
