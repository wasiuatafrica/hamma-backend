# urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('wallet/', views.WalletBalance.as_view(), name='wallet-detail'),
    path('wallet/withdraw/', views.WalletWithdraw.as_view(), name='wallet-withdraw'),
    path("resend-withdraw-otp/", views.ResendWithdrawalOtp.as_view()),
    # path("wallet/summary/", views.GetWalletSummary.as_view(), name="wallet_summary"),
    path('stocks/', views.StockList.as_view(), name='stock-list'),
    path('mini-chart/', views.MiniData.as_view(), name='stock-list'),
    path('single-stock/<str:symbol>/', views.GetSingleStock.as_view(), name='single-stock'),
    path('stocks/<int:pk>/', views.StockDetail.as_view(), name='stock-detail'),
    path('symbols/', views.Symbols.as_view(), name='symbols'),
    # path('portfolio/<str:mode>/', views.PortfolioDetail.as_view(), name='portfolio-detail'),
    path("receipts/", views.ReceiptsView.as_view()),
    path("paystack-receipt/", views.PayStackReceiptsView),
    path('transactions/', views.TransactionList.as_view(), name='transaction-list'),
    path("alert/", views.AlertView.as_view()),
    path("alert/<int:id>/", views.AlertUpdateView.as_view()),
    path("fund-live/", views.FundLiveAccount.as_view()  ),
    path("withdraw-live/", views.WithdrawLiveAccount.as_view() ),
    path('button-click/', views.ButtonClickCreateView.as_view(), name='button-click-create'),
    path('stock-watchlist/', views.StockWatchlistAPIView.as_view(), name='stock-watchlist'),
    path('most-traded/', views.MostTradedStocks.as_view(),),
    
    
    #wallet
    path('wallet/support/<str:email>/', views.SupportWalletBalance.as_view()),
    path("alert/support/<str:email>/", views.SupportAlertView.as_view()),
    path('transactions/support/<str:email>/', views.SupportTransactionList.as_view()),
    
   

]

