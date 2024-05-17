from django.urls import path, include
from django.urls.conf import re_path
from . import views

urlpatterns = [
   path('login/', views.LoginView.as_view(),),
   path("manage-users/", views.AdminManageUser.as_view(), name="manage-users"),
   path("manage-users/<user_id>/", views.AdminManageUser.as_view(), name="manage-users"),
   path('receipts/', views.AdminReceiptsView.as_view()),
   path('withdrawals/', views.WithdrawalView.as_view()),
   path('check-balance/', views.CheckBalance.as_view()),
   path('trades/', views.AdminTradeView.as_view()),
   path("manage-referrals/", views.AdminApproveAndViewRewardActivities.as_view()),
   path("affilate-ranks/", views.AffilateManagement.as_view()),
   path("users-activity-log/<str:id>/", views.UserActivityLogView.as_view()),
   path("users-activity-log/", views.AllUsersActivityLogView.as_view()),
   path("trade-activity-log/<str:id>/", views.UserTradeActivityLog.as_view()),
   path("user-payment-history/<str:id>/", views.UserPaymentActivityLog.as_view()),
   path("user-asset-breakdown/<str:id>/", views.UserAssetBreakDown.as_view()),
   path("analytics/", views.AnalyticsView.as_view()),
   path("analytics/graph/", views.AnalyticsGraphView.as_view()),
   path('user-activity-chart/', views.UserActivityChartData.as_view(), name='user-activity-chart'),
   path("activate-deactivate-account/", views.DeactivateAccount.as_view()),
   path("user-reward-activities/<str:user_id>/", views.RewardActivitiesView.as_view()),
   path("flag-reciept/<str:reciept_id>/", views.FlagReciept.as_view()),
   path("flag-withdrawal-request/<str:withdrawal_request_id>/", views.FlagWithdrawalRequest.as_view()),
   path("admin-users-activity-log/", views.AllAdminUsersActivityLogView.as_view()),
   path("flag-reward-activity/<str:reward_activity_id>/", views.FlagRewardActivities.as_view()),

   #new clan admin links


]
