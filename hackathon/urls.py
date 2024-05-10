from django.urls import path
from . import views
from rest_framework.routers import SimpleRouter


router = SimpleRouter()
router.register('clans', views.ClanViewSet)



urlpatterns=[
    path('competition/', views.CompetitionView.as_view()), #
    path('currentcompetition/', views.CurrentCompetition.as_view() ), #
    path('check/', views.CompetitionCheck.as_view()), #
    path('in-competition/', views.InCompetition.as_view() ), #
    path('can-create-join/', views.CanJoin.as_view()), #
    path('create-clan/', views.CreateClanRequestView.as_view()),
    path('join-clan/', views.JoinClanRequestView.as_view()),
    path('leave-clan/<str:clan_id>/', views.LeaveAClan.as_view()),
    path('transfer-admin/<str:clan_id>/<str:new_admin_id>/', views.TransferAdmin.as_view()),
    path('clan_members/<str:clan_id>/', views.ClanMembers.as_view()), #not complete
    path('join-leave/<str:action>/', views.JoinLeaveCompetetion.as_view()), #
    path('trading-days/', views.TradingDays.as_view()),
    
    path('leaderboard/', views.LeaderBoardView.as_view(),),
    path('clan-payout/',views.ClanPayout.as_view()),
    path('competition-summary/<str:competition_id>/', views.CompetitionSummaryView.as_view()),
    path('competition-summary/<str:competition_id>/<str:clan_id>/', views.CompetitionSummaryViewForClan.as_view()),
    path('request-top-trader-payout/<str:competition_id>/', views.TopTraderPayoutRequest.as_view()),
    path('request-top-clan-payout/<str:competition_id>/', views.TopClanPayoutRequest.as_view()),
    path('trader-payout-history/',views.PayoutHistory.as_view()),
    path('notifications/',views.GetAndUpdateUserNotifications.as_view()),
    path('top-clans/', views.TopClans.as_view()),
    path('top-traders/', views.TopTraders.as_view()),
    
    #admin
    path("login/", views.login_view, name="leaderboard_admin"),
    path("logout/", views.logout_view, name="logout"),
    path('leaderboard-list/', views.leaderboard_view, name='leaderboard'),
    path('remove/<int:pk>/', views.remove_trader, name='remove'),
    path('join-competition/', views.join_competition, name='join-competition'),
    path('users/', views.list_users, name='list-users'),
    path('current_competition_users/<str:id>', views.current_competition_users, name='current_competition_users'),
    path('edit-user/<int:user_id>/', views.edit_user, name='edit-user'),
    # path('traders/', views.all_trader, name='traders'),
    path('create-clan-requests/', views.clan_requests, name='clan-requests'),
    path('all-clan-list/', views.clan_list, name='all-clan-list'),
    path('clan-detail/<int:pk>/', views.clan_detail, name='clan-details'),
    path('clan/<int:pk>/edit/', views.edit_clan, name='edit-clan'),
    path('clan/<int:pk>/delete/', views.delete_clan, name='delete-clan'),
    path('clan-payout-list/', views.clan_payout, name='topclan-payout'),
    path('clan-payout-detail/<int:payout_id>/', views.clan_payout_detail, name='clan-payout-detail'),
    path('trader-payout/', views.trader_payout, name='trader-payout'),
    path('create-competition/',views.create_competition, name='start-competition'),
    path('competition-list/',views.competition_list, name='competition_list'),
    path('payout-details/<str:pk>/', views.payout_details, name='payout-details'),
    path('clan-payout-details/<str:pk>/', views.clan_payout_details, name='clan-payout-details'),
    path('update-toptrader-payout/', views.update_toptrader_payout),
    path('update-topclan-payout/', views.update_topclan_payout),
    path('payout/toptrader/select-competition/', views.competition_list_for_top_trader_payout, name="competition_list_for_top_trader_payout"),
    # path('competition/<str:competition_id>/payout/toptrader/', views.topclan_payout, name="toptrader"),
    path('competition-summary/<str:competition_id>/<str:clan_id>/', views.CompetitionSummaryViewForClan.as_view()),
    

    # New admin views
    path("clan-name-change-requests", views.admin_clan_update_name_link, name="admin_name_change_req"),
    path("clan-name-change-requests/<str:req_id>/", views.admin_clan_update_name_detailed, name="change_name_detailed"),
    path("clan-remove-member-requests", views.admin_clan_remove_member, name="admin_member_req"),
    path("clan-remove-member-requests/<str:req_id>/", views.admin_clan_remove_member_detailed, name="remove_member_detailed"),
    
    
    # new clan endpoints
    path('clan/<str:clan_id>/update-logo-link/', views.ClanUpdateLogoAndLInk.as_view()),
    path('clan/request-name-change/', views.ClanNameChangeRequestView.as_view()),
    path('clan/request-member-removal/', views.ClanMemeberRemoverRequest.as_view()),

    #support
    path('trading-days/support/<str:email>/', views.SupportTradingDays.as_view()),
    path('clan/support/<str:email>/', views.SupportClandetails.as_view()),
    path('join-clan/support/<str:email>/', views.SupportJoinClanRequestView.as_view()),
    path('request-top-trader-payout/<str:competition_id>/support/<str:email>/', views.SupportTopTraderPayoutRequest.as_view()),
    path('request-top-clan-payout/<str:competition_id>/support/<str:email>/', views.SupportTopClanPayoutRequest.as_view()),
    path('trader-payout-history/support/<str:email>/',views.SupportPayoutHistory.as_view()),
    
    
    
    
    

]+router.urls