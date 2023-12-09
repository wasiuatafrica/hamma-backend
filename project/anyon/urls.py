from django.urls import path, include
from django.urls.conf import re_path
from . import views

urlpatterns = [
   path('login/', views.LoginView.as_view(),),
   path("manage-users/", views.AdminManageUser.as_view(), name="manage-users"),
   path("manage-users/<user_id>/", views.AdminManageUser.as_view(), name="manage-users"),
   path('receipts/', views.AdminReceiptsView.as_view()),
   path('withdrawals/', views.WithdrawalView.as_view()),
   path('trades/', views.AdminTradeView.as_view()),
]
