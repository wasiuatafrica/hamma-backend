from django.urls import path
from . import views

urlpatterns = [
    path('trade/demo/', views.DemoTradeAPIView.as_view()),
    path('home/<str:mode>/', views.Home.as_view()),
    path('close/demo/<str:id>/', views.DemoCloseTrade.as_view()),
    path('holding/demo/', views.DemoHolding.as_view())
]
