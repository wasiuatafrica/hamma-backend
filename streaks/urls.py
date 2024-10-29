from django.urls import path
from .views import (
    LeaderboardAPIView,
    UserDailyStreakAPIView,
    UserActivityBadgeAPIView,
    UserRewardAPIView,
)

urlpatterns = [
    path("leaderboard/", LeaderboardAPIView.as_view(), name="leaderboard"),
    path(
        "user-daily-streaks/",
        UserDailyStreakAPIView.as_view(),
        name="user-daily-streaks",
    ),
    path(
        "user-daily-streaks/<int:user_id>/",
        UserDailyStreakAPIView.as_view(),
        name="user-daily-streak-detail",
    ),
    path(
        "user-activity-badges/",
        UserActivityBadgeAPIView.as_view(),
        name="user-activity-badges",
    ),
    path(
        "user-activity-badges/<int:user_id>/",
        UserActivityBadgeAPIView.as_view(),
        name="user-activity-badge-detail",
    ),
    path("user-rewards/", UserRewardAPIView.as_view(), name="user-rewards"),
    path(
        "user-rewards/<int:user_id>/",
        UserRewardAPIView.as_view(),
        name="user-reward-detail",
    ),
]
