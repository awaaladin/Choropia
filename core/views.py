from pathlib import Path

from django.conf import settings
from django.http import Http404, HttpResponse
from django.views import View

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
        return HttpResponse(html)
