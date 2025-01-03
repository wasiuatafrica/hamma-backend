from django.urls import path
from . import views

urlpatterns = [
    # path("trade/demo/", views.DemoTradeAPIView.as_view()),
    # path("home/<str:mode>/", views.Home.as_view()),
    # path("close/demo/<str:id>/", views.DemoCloseTrade.as_view()),
    # path("cancel/demo/<str:id>/", views.DemoClosePendingTrade.as_view()),
    # path("holding/demo/", views.DemoHolding.as_view()),
    path("home/<str:mode>/support/<str:email>/", views.SupportHome.as_view()),
    path("holding/demo/support/<str:email>/", views.SupportDemoHolding.as_view()),
    path("trade/demo/support/<str:email>/", views.SupportDemoTradeAPIView.as_view()),
    path("demo/accounts/", views.DemoPorfoliosAccounts.as_view()),
    path("live/accounts/", views.PorfoliosAccounts.as_view()),
    path("demo/account/<str:id>/", views.RetrieveSingleDemoPorfoliosAccounts.as_view()),
    path("live/account/<str:id>/", views.RetrieveSinglePorfoliosAccounts.as_view()),
    path(
        "demo/trade/<str:account_type>/<str:id>/",
        views.SingleDemoTradeAPIView.as_view(),
    ),
    path("demo/home/trade/<str:account_type>/<str:id>/", views.NewHome.as_view()),
    path(
        "demo/home/overview/<str:account_type>/<str:id>/<str:from_date>/<str:to_date>/",
        views.NewOverView.as_view(),
    ),
    path(
        "demo/close/trade/<str:account_type>/<str:id>/<str:position_id>/",
        views.NewDemoCloseTrade.as_view(),
    ),
    path(
        "demo/cancel/trade/<str:account_type>/<str:id>/<str:position_id>/",
        views.NewDemoClosePendingTrade.as_view(),
    ),
    path("demo/holding/<str:account_type>/<str:id>/", views.NewDemoHolding.as_view()),
    path("trailing-sl/<str:id>/", views.AddTrailingStopLoss.as_view()),
    path("create-competition-account/", views.CreatCompetitionAccount.as_view()),
    path("leave-competition/", views.LeaveCompetion.as_view()),
    path(
        "competition/account/<str:id>/", views.RetrieveSIngleCompetitonAccount.as_view()
    ),
    path("activate-prop-account/", views.ActivatePropAccountView.as_view()),
    path(
        "demo/support/home/<str:account_type>/<str:id>/", views.NewSupportHome.as_view()
    ),
    path(
        "demo/support/accounts/<str:email>/",
        views.SupportDemoPorfoliosAccounts.as_view(),
    ),
    path(
        "demo/support/holding/<str:account_type>/<str:id>/",
        views.NewSupportDemoHolding.as_view(),
    ),
    path(
        "demo/support/trade/<str:account_type>/<str:id>/",
        views.SupportSingleDemoTradeAPIView.as_view(),
    ),
    path(
        "demo/support/overview/<str:account_type>/<str:id>/<str:from_date>/<str:to_date>/",
        views.SupportNewOverView.as_view(),
    ),
]
