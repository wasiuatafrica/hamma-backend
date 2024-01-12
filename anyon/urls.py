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
   path("manage-referrals/", views.AdminApproveAndViewRewardActivities.as_view()),
   path("affilate-ranks/", views.AffilateManagement.as_view()),
   path("users-activity-log/<str:id>/", views.UserActivityLogView.as_view()),
   path("users-activity-log/", views.AllUsersActivityLogView.as_view()),
   path("trade-activity-log/<str:id>/", views.UserTradeActivityLog.as_view()),
   path("user-payment-history/<str:id>/", views.UserPaymentActivityLog.as_view()),
   path("user-asset-breakdown/<str:id>/", views.UserAssetBreakDown.as_view()),

]
