from unittest import mock

import requests
from django.core.cache import cache
from django.test import TestCase, override_settings

BASE = "https://store123.public.blob.vercel-storage.com"


class ApkRedirectTests(TestCase):
    @override_settings(BLOB_PUBLIC_BASE_URL=BASE)
    def test_download_path_redirects_to_the_blob_apk_as_an_attachment(self):
        response = self.client.get("/downloads/choropia.apk")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], f"{BASE}/downloads/choropia.apk?download=1")
        self.assertIn("no-store", response["Cache-Control"])

    @override_settings(BLOB_PUBLIC_BASE_URL=BASE)
    def test_head_request_also_works(self):
        self.assertEqual(self.client.head("/downloads/choropia.apk").status_code, 302)

    @override_settings(BLOB_PUBLIC_BASE_URL="")
    def test_without_storage_it_says_not_available_instead_of_serving_the_spa(self):
        response = self.client.get("/downloads/choropia.apk")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response["Content-Type"], "application/json")


@override_settings(BLOB_PUBLIC_BASE_URL=BASE)
class AndroidAppInfoTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    @mock.patch("common.app_download.requests.get")
    def test_returns_version_size_and_checksum_and_caches_it(self, get):
        get.return_value = mock.Mock(ok=True)
        get.return_value.json.return_value = {"version": "1.2.0", "version_code": 3, "size_bytes": 19_000_000, "sha256": "ab" * 32}

        first = self.client.get("/api/v1/app/android/")
        second = self.client.get("/api/v1/app/android/")

        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json()["version"], "1.2.0")
        self.assertEqual(first.json()["sha256"], "ab" * 32)
        self.assertEqual(first.json()["min_android"], "8.0")
        self.assertEqual(first.json()["download_url"], "/downloads/choropia.apk")
        self.assertEqual(second.json(), first.json())
        self.assertEqual(get.call_count, 1)  # the second answer came from the cache

    @mock.patch("common.app_download.requests.get")
    def test_404_when_no_build_has_been_published(self, get):
        get.return_value = mock.Mock(ok=False)
        self.assertEqual(self.client.get("/api/v1/app/android/").status_code, 404)

    @mock.patch("common.app_download.requests.get", side_effect=requests.ConnectionError("down"))
    def test_storage_outage_is_a_404_not_a_500(self, get):
        self.assertEqual(self.client.get("/api/v1/app/android/").status_code, 404)

    def test_needs_no_login(self):
        with mock.patch("common.app_download.requests.get") as get:
            get.return_value = mock.Mock(ok=True)
            get.return_value.json.return_value = {"version": "1.0"}
            self.assertEqual(self.client.get("/api/v1/app/android/").status_code, 200)
