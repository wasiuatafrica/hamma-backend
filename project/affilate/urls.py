from django.urls import path
from . import views


urlpatterns=[
    # path("my_referal_link/", views.MyRefferalLink.as_view(), name="my_referal_link"),
    # path("invite-friend/", views.InviteFriend.as_view(),name="nvite-friend"),
    path("reward-activities/", views.RewardActivitiesView.as_view(), name='reward-activities'),
    path("ranking/", views.RankingView.as_view(), name='ranking'),
    path("home/", views.HomeView.as_view(), name='home'),
    path('withdraw/', views.ReferralWithdrawal.as_view())
    

]