from django.urls import path
from . import views

urlpatterns = [
    # path("trading-ai/", views.TradeRecommendationView.as_view(), name="trading-ai"),
    path(
        "trading-ai-sub/", views.TradeRecommendationViewSub.as_view(), name="trading-ai"
    ),
]
