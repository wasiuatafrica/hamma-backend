# asgi.py
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")
django.setup()

from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from notifications import routing
from portfolio import routing as alerti
from execution import routing as trading
from supportwithemail import routing as no_auth_access_support

application = ProtocolTypeRouter(
    {
        "http": get_asgi_application(),
        "websocket": AuthMiddlewareStack(
            URLRouter(
                routing.websocket_urlpatterns
                + alerti.websocket_urlpatterns
                + trading.websocket_urlpatterns
                + no_auth_access_support.websocket_urlpatterns
            )
        ),
    }
)
