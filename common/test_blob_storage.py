from unittest import mock

import requests
from django.core.files.base import ContentFile
from django.test import SimpleTestCase, override_settings

from common.blob_storage import VercelBlobStorage
from common.exceptions import is_storage_failure
from common.storage_errors import StorageUnavailable

BASE = "https://store123.public.blob.vercel-storage.com"


def storage():
    return VercelBlobStorage(token="test-token", base_url=BASE)


class VercelBlobStorageTests(SimpleTestCase):
    @mock.patch("common.blob_storage.requests.put")
    def test_save_uploads_bytes_and_returns_the_pathname_blob_chose(self, put):
        put.return_value = mock.Mock(ok=True, status_code=200)
        put.return_value.json.return_value = {"pathname": "listings/photo-AbC123.jpg", "url": f"{BASE}/listings/photo-AbC123.jpg"}

        saved = storage().save("listings/photo.jpg", ContentFile(b"jpegbytes"))

        self.assertEqual(saved, "listings/photo-AbC123.jpg")  # what Django stores in the DB column
        args, kwargs = put.call_args
        self.assertEqual(kwargs["params"], {"pathname": "listings/photo.jpg"})
        self.assertEqual(kwargs["data"], b"jpegbytes")
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer test-token")
        self.assertEqual(kwargs["headers"]["x-vercel-blob-access"], "public")
        self.assertEqual(kwargs["headers"]["x-add-random-suffix"], "1")
        self.assertEqual(kwargs["headers"]["x-content-type"], "image/jpeg")

    def test_url_is_public_host_plus_encoded_pathname(self):
        self.assertEqual(storage().url("chat/voice note-1.m4a"), f"{BASE}/chat/voice%20note-1.m4a")

    @mock.patch("common.blob_storage.requests.put")
    def test_rejected_upload_is_a_storage_failure(self, put):
        put.return_value = mock.Mock(ok=False, status_code=403, text="forbidden")
        with self.assertRaises(StorageUnavailable) as caught:
            storage().save("a.jpg", ContentFile(b"x"))
        self.assertTrue(is_storage_failure(caught.exception))

    @mock.patch("common.blob_storage.requests.put", side_effect=requests.ConnectionError("down"))
    def test_network_failure_is_a_storage_failure(self, put):
        with self.assertRaises(StorageUnavailable):
            storage().save("a.jpg", ContentFile(b"x"))

    @mock.patch("common.blob_storage.requests.post")
    def test_delete_is_best_effort(self, post):
        post.side_effect = requests.ConnectionError("down")
        storage().delete("a.jpg")  # must not raise
        post.side_effect = None
        post.return_value = mock.Mock(ok=False)
        storage().delete("a.jpg")  # must not raise either

    @override_settings(BLOB_READ_WRITE_TOKEN="")
    def test_missing_token_is_reported_not_crashed(self):
        with self.assertRaises(StorageUnavailable):
            VercelBlobStorage(base_url=BASE).save("a.jpg", ContentFile(b"x"))

    def test_names_never_clash(self):
        self.assertFalse(storage().exists("anything"))
        self.assertEqual(storage().get_available_name("a.jpg"), "a.jpg")
