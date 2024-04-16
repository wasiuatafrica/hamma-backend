from django.urls import path
from . import views

urlpatterns = [
    path('trade/demo/', views.DemoTradeAPIView.as_view()),
    path('home/<str:mode>/', views.Home.as_view()),
    path('close/demo/<str:id>/', views.DemoCloseTrade.as_view()),
    path('cancel/demo/<str:id>/', views.DemoClosePendingTrade.as_view()),
    path('holding/demo/', views.DemoHolding.as_view()),
    
    #support
    path('home/<str:mode>/support/<str:email>/', views.SupportHome.as_view()),
    path('holding/demo/support/<str:email>/', views.SupportDemoHolding.as_view())
]
