from django.test import TestCase



class AssetLinksTests(TestCase):
    def test_serves_android_app_links_file(self):
        r = self.client.get("/.well-known/assetlinks.json")
        self.assertEqual(r.status_code, 200)
        target = r.json()[0]["target"]
        self.assertEqual(target["package_name"], "com.choropia.app")
        self.assertTrue(target["sha256_cert_fingerprints"])
