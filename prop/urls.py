from django.urls import path
from . import views
from rest_framework import routers
from .views import MyReferralWalletManagement

# router = routers.DefaultRouter()
# router.register(
#     "referral-wallet", MyReferralWalletManagement, basename="referral-wallet"
# )


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
    path(
        "referral-wallet/balance/",
        MyReferralWalletManagement.as_view({"get": "wallet_balance"}),
        name="wallet-balance",
    ),
    path(
        "referral-wallet/reward-activities/",
        MyReferralWalletManagement.as_view({"get": "reward_activities"}),
        name="referral-activities",
    ),
    path(
        "referral-wallet/request-payout/",
        MyReferralWalletManagement.as_view({"post": "request_referral_reward_payout"}),
        name="request-payout",
    ),
    path(
        "referral-wallet/payout-requests/",
        MyReferralWalletManagement.as_view({"get": "my_referral_payout_request_lists"}),
        name="payout-requests",
    ),
    path("user-receipts/", views.UserReceiptsView.as_view()),
]

# # Add router URLs to urlpatterns
# urlpatterns += router.urls
