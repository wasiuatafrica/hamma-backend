from django.urls import path
from . import views

urlpatterns = [
    path("trading-ai/", views.TradeRecommendationView.as_view(), name="trading-ai")
]
