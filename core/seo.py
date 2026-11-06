"""Search-engine plumbing: robots.txt, sitemap.xml, and per-listing page titles in the HTML the crawler first receives."""
import html
import re
from xml.sax.saxutils import escape

from django.conf import settings
from django.http import HttpResponse

PUBLIC_PAGES = ["/", "/marketplace", "/about", "/how-it-works", "/contact", "/privacy", "/get-app", "/reels"]
LISTING_PATH = re.compile(r"^/listings/(\d+)/?$")


def site_url():
    return settings.CHOROPIA_SITE_URL.rstrip("/")


def robots_txt(request):
    body = "\n".join(
        [
            "User-agent: *",
            "Allow: /",
            "Disallow: /api/",
            "Disallow: /staff/",
            "Disallow: /pay/",
            "Disallow: /login",
            "Disallow: /register",
            "Disallow: /profile",
            "Disallow: /orders",
            "Disallow: /messages",
            f"Sitemap: {site_url()}/sitemap.xml",
            "",
        ]
    )
    return HttpResponse(body, content_type="text/plain")


def sitemap_xml(request):
    from listings.models import Listing

    base = site_url()
    urls = [(f"{base}{path}", None) for path in PUBLIC_PAGES]
    listings = Listing.objects.filter(status=Listing.Status.ACTIVE).order_by("-created_at")[:2000]
    urls += [(f"{base}/listings/{l.pk}", l.updated_at) for l in listings]
    rows = []
    for loc, modified in urls:
        last = f"<lastmod>{modified.date().isoformat()}</lastmod>" if modified else ""
        rows.append(f"<url><loc>{escape(loc)}</loc>{last}</url>")
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + "".join(rows) + "</urlset>"
    return HttpResponse(xml, content_type="application/xml")


def listing_page_html(page_html, path):
    """For /listings/<id>, put the listing's own title and description into the page head so search results and link
    previews (WhatsApp, Facebook) show the item instead of the generic site text. Any failure leaves the page untouched."""
    match = LISTING_PATH.match(path)
    if not match:
        return page_html
    try:
        from listings.models import Listing

        listing = Listing.objects.select_related("owner").prefetch_related("photos").filter(pk=int(match.group(1))).exclude(status=Listing.Status.REMOVED).first()
        if listing is None:
            return page_html
        title = html.escape(f"{listing.title} | Choropia", quote=True)
        price = f"₦{listing.price:,.0f}"
        description = html.escape(f"{price}. {(listing.description or 'For sale on Choropia, with escrow-protected payment.')[:150]}", quote=True)
        photo = listing.photos.first()
        image = html.escape(photo.image.url if photo else f"{site_url()}/favicon-512.png", quote=True)
        page_html = re.sub(r"<title>.*?</title>", f"<title>{title}</title>", page_html, count=1, flags=re.S)
        page_html = re.sub(r'<meta\s+name="description"[^>]*>', f'<meta name="description" content="{description}" />', page_html, count=1, flags=re.S)
        for prop, value in (("og:title", title), ("og:description", description), ("og:image", image), ("og:url", f"{site_url()}/listings/{listing.pk}")):
            page_html = re.sub(rf'<meta\s+property="{prop}"[^>]*>', f'<meta property="{prop}" content="{value}" />', page_html, count=1)
        page_html = re.sub(r'<link\s+rel="canonical"[^>]*>', f'<link rel="canonical" href="{site_url()}/listings/{listing.pk}" />', page_html, count=1)
        return page_html
    except Exception:  # noqa: BLE001 - SEO tags must never take the page down
        return page_html
