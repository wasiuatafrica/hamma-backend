# asgi.py
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")
django.setup()

from django.conf import settings
from django.core.asgi import get_asgi_application

if settings.CELERY_TASK_ALWAYS_EAGER:
    # Tasks run inside this process, from several threads. Celery binds tasks
    # lazily on first use and that isn't thread-safe, so load and bind them all
    # now, while startup is still single-threaded.
    from backend.celery import app as celery_app

    celery_app.loader.import_default_modules()
    celery_app.finalize()
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
