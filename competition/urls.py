from django.urls import path
from . import views

urlpatterns = [
    path('competition/', views.CompetitionView.as_view()),
    path('join-leave/<int:competition_id>/<str:action>/', views.JoinLeaveCompetetion.as_view()),
    path('wallet/', views.WalletBalance.as_view()),
    path('check/', views.CompetitionCheck.as_view()),
    path('trading-days/', views.TradingDays.as_view()),
    path('leaderboard/', views.Leaderboard.as_view()),
  
]
