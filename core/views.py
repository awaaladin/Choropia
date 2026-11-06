from pathlib import Path

from django.conf import settings
from django.http import Http404, HttpResponse
from django.views import View

# Only our own scripts may run on the website, which limits what an injected script could do. (Styles allow inline because the
# UI libraries set style attributes; images and media may come from any https host because listing photos live in storage.)
CONTENT_SECURITY_POLICY = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
        "font-src 'self' data: https://fonts.gstatic.com",
        "img-src 'self' data: blob: https:",
        "media-src 'self' blob: https:",
        "connect-src 'self' https: wss:",
        "frame-ancestors 'none'",
        "base-uri 'self'",
        "object-src 'none'",
        "form-action 'self'",
    ]
)

_INDEX_PATH = Path(settings.BASE_DIR) / "frontend" / "dist" / "index.html"


class SPAView(View):
    """Serves the built React app's index.html for every non-API route, so React Router
    handles the path client-side. The app's own JS/CSS/image files are matched and served
    directly by WhiteNoiseMiddleware (WHITENOISE_ROOT) before a request ever reaches here —
    this view only runs for paths that aren't real files, i.e. actual app routes."""

    def get(self, request, *args, **kwargs):
        try:
            html = _INDEX_PATH.read_text(encoding="utf-8")
        except FileNotFoundError:
            raise Http404(
                "frontend/dist/index.html not found — run `npm run build` in frontend/ "
                "(and commit the output; Vercel doesn't run the frontend build itself)."
            )
        from .seo import listing_page_html

        response = HttpResponse(listing_page_html(html, request.path))
        response["Content-Security-Policy"] = CONTENT_SECURITY_POLICY
        response["Permissions-Policy"] = "camera=(), microphone=(self), geolocation=(self)"
        return response
