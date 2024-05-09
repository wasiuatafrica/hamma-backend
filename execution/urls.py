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
    path('holding/demo/support/<str:email>/', views.SupportDemoHolding.as_view()),
    path('trade/demo/support/<str:email>/', views.SupportDemoTradeAPIView.as_view()),



    ################ NEW demo account urls ########################
    path("demo/accounts/", views.DemoPorfoliosAccounts.as_view()),
    path("demo/account/<str:id>/", views.RetrieveSingleDemoPorfoliosAccounts.as_view()),
    path('demo/trade/<account_type>/<str:id>/', views.SingleDemoTradeAPIView.as_view()),
    # new home view
    path('demo/home/trade/<account_type>/<str:id>/', views.NewHome.as_view()),
    # new close trade view
    path('demo/close/trade/<account_type>/<str:id>/', views.NewDemoCloseTrade.as_view()),
    # new calcle demo pending trade
    path('demo/cancel/trade/<account_type>/<str:id>/', views.NewDemoClosePendingTrade.as_view()),
    # new demohoding view 
    path('demo/holding/<account_type>/<str:id>/', views.NewDemoHolding.as_view()),

    # competition
    path("create-competition-account/", views.CreatCompetitionAccount.as_view()),
    path("leave-competition/", views.LeaveCompetion.as_view()),
    path("competition/account/<str:id>/", views.RetrieveSIngleCompetitonAccount.as_view()),
    

    
]
