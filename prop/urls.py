from django.urls import path
from . import views
from rest_framework import routers
from .views import MyReferralWalletManagement
from . import admin_views
from . import support_views
from . import analytics_views


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
        "admin-payouts/<int:pk>/",
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
    # prop additional admin routes
    path(
        "referral/withdrawal-requests/",
        admin_views.ReferralPayoutManagement.as_view(
            {"get": "referral_payout_request_lists"}
        ),
    ),
    path(
        "referral/withdrawal-requests/<int:pk>/",
        admin_views.ReferralPayoutManagement.as_view({"put": "update_request_status"}),
    ),
    path("user-receipts/", views.UserReceiptsView.as_view()),
    path(
        "support-user-receipts/<email>/", views.SupportSingleUserReceiptsView.as_view()
    ),
    path(
        "payout-request-status/<portfolio_id>/",
        views.PayoutsSummaryView.as_view(),
    ),
    path("activate/", views.ActivateProp.as_view()),
    path(
        "swap-to-balance-drawdown/<int:portfolio_id>/",
        views.ToggleDrawdownMethodView.as_view(),
    ),
    path(
        "admin-payouts/",
        views.AdminPayoutListAPIView.as_view(),
    ),
    path("prop-users/<user_id>/", views.AdminUserList.as_view()),
    path("prop-users/", views.AdminUserList.as_view()),
    # path("pending-receipts/", views.UserPendingReceipts.as_view()),
    path(
        "support-accountlist/<email>/", support_views.SupportUserAccounctsList.as_view()
    ),
    path("hamma-request/<account_id>/", views.HammaAccountRequestView.as_view()),
    path(
        "admin-hamma-requests/",
        admin_views.HammaRequestAdminView.as_view(),
        name="hamma-requests",
    ),  # GET for listing
    path("analytics/", analytics_views.DemoAnalyticsView.as_view()),
    path("graph/", analytics_views.DemoPortfolioAnalyticsView.as_view()),
    path("analytics2/", analytics_views.DemoStatsAPIView.as_view()),
    path("barchart/", analytics_views.PortfoliosByTypeView.as_view()),
    # NEW
    path("new-support-payoutlist/", views.PayoutListAPIView2.as_view()),
    # ref
    path("referral/code/", views.ReferralCodeView.as_view()),
    path("referral/balance/", views.ReferralBalanceView.as_view()),
    path("referral/users/", views.ReferredUsersView.as_view()),
    path("referral/withdraw/", views.WithdrawalRequestView.as_view()),
    path("referral/history/", views.ReferralHistoryView.as_view()),
    path(
        "admin/withdrawal-requests/",
        admin_views.AdminWithdrawalRequestListView.as_view(),
        name="admin-withdrawal-requests",
    ),
    path(
        "admin/withdrawal-requests/<int:request_id>/",
        admin_views.AdminWithdrawalRequestUpdateView.as_view(),
        name="admin-withdrawal-request-update",
    ),
]
