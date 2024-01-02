# urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('wallet/', views.WalletBalance.as_view(), name='wallet-detail'),
    # path('wallet/deposit/', views.WalletDeposit.as_view(), name='wallet-deposit'),
    path('wallet/withdraw/', views.WalletWithdraw.as_view(), name='wallet-withdraw'),
    # path('stocks/', views.async_get_view, name='stock-list'),
    path('stocks/', views.StockList.as_view(), name='stock-list'),
    path('mini-chart/', views.MiniData.as_view(), name='stock-list'),
    path('single-stock/<str:symbol>/', views.GetSingleStock.as_view(), name='single-stock'),
    path('stocks/<int:pk>/', views.StockDetail.as_view(), name='stock-detail'),
    path('symbols/', views.Symbols.as_view(), name='symbols'),
    # path('holdings/', views.HoldingListCreate.as_view(), name='holding-list-create'),
    # path('holdings/<int:pk>/', views.HoldingDetail.as_view(), name='holding-detail'),
    path('portfolio/', views.PortfolioDetail.as_view(), name='portfolio-detail'),
    path("receipts/", views.ReceiptsView.as_view()),
    path("paystack-receipt/", views.PayStackReceiptsView),
    path('transactions/', views.TransactionList.as_view(), name='transaction-list'),
    path("alert/", views.AlertView.as_view()),
    path("alert/<int:id>/", views.AlertUpdateView.as_view()),


]

