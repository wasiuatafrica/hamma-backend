# urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('wallet/', views.WalletBalance.as_view(), name='wallet-detail'),
    path('wallet/withdraw/', views.WalletWithdraw.as_view(), name='wallet-withdraw'),
    path('stocks/', views.StockList.as_view(), name='stock-list'),
    path('mini-chart/', views.MiniData.as_view(), name='stock-list'),
    path('single-stock/<str:symbol>/', views.GetSingleStock.as_view(), name='single-stock'),
    path('stocks/<int:pk>/', views.StockDetail.as_view(), name='stock-detail'),
    path('symbols/', views.Symbols.as_view(), name='symbols'),
    path('portfolio/<str:mode>/', views.PortfolioDetail.as_view(), name='portfolio-detail'),
    path("receipts/", views.ReceiptsView.as_view()),
    path("paystack-receipt/", views.PayStackReceiptsView),
    path('transactions/', views.TransactionList.as_view(), name='transaction-list'),
    path("alert/", views.AlertView.as_view()),
    path("alert/<int:id>/", views.AlertUpdateView.as_view()),
   

]

