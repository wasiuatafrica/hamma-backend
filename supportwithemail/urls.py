from django.urls import path
from . import views

urlpatterns = [
    # path('sse/', sse.index, name='index'),
    path("bot/rate-response/", views.RateBotResponse.as_view()),
    path("switch-back-to-ai-bot/<int:thread>", views.SwitchBackToAIBot.as_view()),
    # path('stream/', sse.sse_stream, name='sse_stream'),
]