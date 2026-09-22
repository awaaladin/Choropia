import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")

from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from django.core.asgi import get_asgi_application  # noqa: E402

django_asgi_app = get_asgi_application()

from common.ws_auth import JWTAuthMiddlewareStack  # noqa: E402
import chat.routing  # noqa: E402
import notifications.routing  # noqa: E402

websocket_urlpatterns = chat.routing.websocket_urlpatterns + notifications.routing.websocket_urlpatterns

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": JWTAuthMiddlewareStack(URLRouter(websocket_urlpatterns)),
    }
)
