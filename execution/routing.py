# routing.py
from django.urls import re_path

from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/markets-ai/$', consumers.MarketConsumer2.as_asgi()),
]