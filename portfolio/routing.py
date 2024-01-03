# routing.py
from django.urls import re_path

from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/alerts-ai/$', consumers.AlertConsumer.as_asgi()),
]
