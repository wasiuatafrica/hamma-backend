from django.urls import path
from .views import (
    LeaderboardAPIView,
    UserActivityBadgeAPIView,
    UserRewardAPIView,
)
from django.urls import path
from .views import CurrentStreakAPIView, LongestStreakAPIView, StreakCalendarAPIView

urlpatterns = [
    path("current-streak/", CurrentStreakAPIView.as_view(), name="current-streak"),
    path("longest-streak/", LongestStreakAPIView.as_view(), name="longest-streak"),
    path("streak-calendar/", StreakCalendarAPIView.as_view(), name="streak-calendar"),
    path("leaderboard/", LeaderboardAPIView.as_view(), name="leaderboard"),
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
