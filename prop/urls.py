from django.urls import path
from . import views

urlpatterns = [
    path(
        "account-data/<account_id>/",
        views.AccountDataView.as_view(),
    ),
    path("metrics/<portfolio_id>/", views.PortfolioMetrics.as_view()),
    path(
        "payouts/",
        views.PayoutListAPIView.as_view(),
    ),
    path(
        "payouts/<int:pk>/",
        views.PayoutDetailAPIView.as_view(),
    ),
    path(
        "payouts/request/",
        views.RequestPayoutAPIView.as_view(),
    ),
    path(
        "payouts/<int:pk>/process/",
        views.ProcessPayoutAPIView.as_view(),
    ),
    path(
        "prop-receipts/",
        views.AdminReceiptsView.as_view(),
    ),
    path("accountlist/", views.AdminAccountsList.as_view()),
    path("user-accountlist/", views.UserAccounctsList.as_view()),
    path("daily-profits/<portfolio_id>/", views.PortfolioDailyProfitLossView.as_view()),
]
