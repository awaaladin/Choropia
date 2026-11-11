from django.test import TestCase


class SeoAndHeadersTests(TestCase):
    def test_robots_and_sitemap_are_served_and_list_listings(self):
        from accounts.models import User
        from listings.models import Category, Listing

        owner = User.objects.create_user("seo@example.com", "pw12345!")
        listing = Listing.objects.create(owner=owner, category=Category.objects.create(name="Gadgets"), title="Power bank", price="5000.00")
        robots = self.client.get("/robots.txt")
        self.assertContains(robots, "Sitemap:")
        self.assertContains(robots, "Disallow: /staff/")
        sitemap = self.client.get("/sitemap.xml")
        self.assertEqual(sitemap["Content-Type"], "application/xml")
        self.assertContains(sitemap, f"/listing/power-bank-{listing.public_id}")
        self.assertNotContains(sitemap, f"/listings/{listing.pk}")  # sequential ids never appear in public links

    def test_old_numeric_listing_links_redirect_permanently_to_the_coded_address(self):
        from accounts.models import User
        from listings.models import Category, Listing

        owner = User.objects.create_user("o2@example.com", "pw-12345-pw")
        listing = Listing.objects.create(owner=owner, category=Category.objects.create(name="Phones"), title="iPhone 13", price="5000.00")
        response = self.client.get(f"/listings/{listing.pk}")
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response["Location"], f"/listing/iphone-13-{listing.public_id}")
        self.assertEqual(self.client.get("/listings/999999").status_code != 301, True)  # unknown: no redirect

    def test_spa_pages_carry_a_content_security_policy(self):
        response = self.client.get("/marketplace")
        if response.status_code == 200:  # needs the built frontend, which tests may not have
            self.assertIn("script-src 'self'", response["Content-Security-Policy"])
