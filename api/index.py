"""
Vercel serverless entrypoint.

Vercel's Python runtime only hosts plain request/response HTTP functions — it cannot run
Django Channels' WebSocket consumers or Celery workers/beat. So under this deployment:
  - Chat and notification WebSockets (config/asgi.py, normally served by daphne) don't work.
  - Background jobs (escrow auto-release, gaxtron payment polling — see payments/tasks.py)
    never run, since there's no long-lived worker process here.
Both still run wherever the repo's Dockerfile/docker-compose stack is hosted; this entrypoint
only serves ordinary HTTP — the web frontend and the parts of the API that don't need a
persistent connection.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")

from django.core.wsgi import get_wsgi_application  # noqa: E402

app = get_wsgi_application()
application = app
