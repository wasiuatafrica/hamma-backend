# routing.py
from django.urls import re_path

from . import consumers
from . import adminConsumer

websocket_urlpatterns = [
    re_path(r"ws/no-auth-support/$", consumers.NoAuthSupportConsumer.as_asgi()),
    re_path(r"ws/admin-support/$", adminConsumer.AdminSupportConsumer.as_asgi()),
]
