from django.urls import path
from .views import DemoTradeAPIView

urlpatterns = [
    path('demo/', DemoTradeAPIView.as_view(), name='trade-api'),
]
