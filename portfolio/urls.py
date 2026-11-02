# urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("wallet/", views.WalletBalance.as_view(), name="wallet-detail"),
    path("wallet/withdraw/", views.WalletWithdraw.as_view(), name="wallet-withdraw"),
    path("resend-withdraw-otp/", views.ResendWithdrawalOtp.as_view()),
    # path("wallet/summary/", views.GetWalletSummary.as_view(), name="wallet_summary"),
    path("stocks/", views.StockList.as_view(), name="stock-list"),
    path("mini-chart/", views.MiniData.as_view(), name="stock-list"),
    path(
        "single-stock/<str:symbol>/",
        views.GetSingleStock.as_view(),
        name="single-stock",
    ),
    path(
        "shares-outstanding/",
        views.SharesOutstandingView.as_view(),
        name="shares-outstanding-all",
    ),
    path(
        "shares-outstanding/<str:symbol>/",
        views.SharesOutstandingView.as_view(),
        name="shares-outstanding-symbol",
    ),
    path("stocks/<int:pk>/", views.StockDetail.as_view(), name="stock-detail"),
    path("symbols/", views.Symbols.as_view(), name="symbols"),
    # path('portfolio/<str:mode>/', views.PortfolioDetail.as_view(), name='portfolio-detail'),
    path("receipts/", views.ReceiptsView.as_view()),
    path("paystack-receipt/", views.PayStackReceiptsView),
    path("transactions/", views.TransactionList.as_view(), name="transaction-list"),
    path("alert/", views.AlertView.as_view()),
    path(
        "admin/toggle-data-source/",
        views.ToggleDataSourceView.as_view(),
        name="toggle-data-source",
    ),
    path(
        "data-source-status/",
        views.DataSourceStatusView.as_view(),
        name="data-source-status",
    ),
    path("market-status/", views.MarketStatusView.as_view(), name="market-status"),
    path(
        "collector-symbols/",
        views.CollectorSymbolsView.as_view(),
        name="collector-symbols",
    ),
    path("alert/<int:id>/", views.AlertUpdateView.as_view()),
    path("fund-live/", views.FundLiveAccount.as_view()),
    path("withdraw-live/", views.WithdrawLiveAccount.as_view()),
    path(
        "button-click/",
        views.ButtonClickCreateView.as_view(),
        name="button-click-create",
    ),
    path(
        "stock-watchlist/",
        views.StockWatchlistAPIView.as_view(),
        name="stock-watchlist",
    ),
    path(
        "most-traded/",
        views.MostTradedStocks.as_view(),
    ),
    path("feeds/admin/", views.FeedView.as_view()),
    path("feeds/search/", views.SearchFeedView.as_view(), name="feed-search"),
    path("feeds/publish/", views.PublishFeed.as_view()),
    path("feeds/unpublish/", views.UnpublishFeed.as_view()),
    path("feeds/category/", views.FeedCategoryView.as_view()),
    path(
        "feeds/subscribe/",
        views.SubscribeCategoryAPIView.as_view(),
        name="subscribe_category",
    ),
    path(
        "feeds/unsubscribe/",
        views.UnsubscribeCategoryAPIView.as_view(),
        name="unsubscribe_category",
    ),
    path(
        "feeds/users/",
        views.UserDashboardFeedsAPIView.as_view(),
        name="user_dashboard_feeds",
    ),
    path(
        "feeds/reactions/<str:feed_id>/",
        views.DashboardFeedReactionAPIView.as_view(),
        name="dashboard_feed_reaction",
    ),
    path(
        "reactions/check/<str:feed_id>/",
        views.CheckReaction.as_view(),
    ),
    path("view-other-ideas-log/", views.VIewotherIdeasLogView.as_view()),
    # support
    path("wallet/support/<str:email>/", views.SupportWalletBalance.as_view()),
    path("alert/support/<str:email>/", views.SupportAlertView.as_view()),
    path("transactions/support/<str:email>/", views.SupportTransactionList.as_view()),
    path(
        "support/stock-watchlist/<str:email>/",
        views.SupportStockWatchlistAPIView.as_view(),
    ),
    # track trading ideas
    path(
        "asset/<int:user_id>/<int:feed_id>",
        views.track_daily_mail,
        name="track_daily_mail",
    ),
    path(
        "popular-stocks/",
        views.PopularStocks.as_view(),
        name="popular-stocks",
    ),
]
