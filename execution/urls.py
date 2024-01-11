from django.urls import path
from .views import DemoTradeAPIView

urlpatterns = [
    path('trade/<str:mode>/', DemoTradeAPIView.as_view(), name='trade-api'),
]
