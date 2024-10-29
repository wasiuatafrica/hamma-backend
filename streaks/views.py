from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from .models import UserDailyStreak, UserActivityBadge, Leaderboard, Reward
from .serializers import (
    UserDailyStreakSerializer,
    UserActivityBadgeSerializer,
    LeaderboardSerializer,
    RewardSerializer,
)


class LeaderboardAPIView(APIView):
    def get(self, request):
        # Get the current week's leaderboard data
        current_week_start = timezone.now().date() - timezone.timedelta(
            days=timezone.now().date().weekday()
        )
        leaderboard = Leaderboard.objects.filter(
            week_start_date=current_week_start
        ).order_by("position")
        serializer = LeaderboardSerializer(leaderboard, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class UserDailyStreakAPIView(APIView):
    def get(self, request, user_id=None):
        if user_id:
            # Fetch streak data for a specific user
            streak = UserDailyStreak.objects.filter(user__id=user_id).first()
            if not streak:
                return Response(
                    {"error": "User daily streak not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )
            serializer = UserDailyStreakSerializer(streak)
        else:
            # Fetch streak data for all users
            streaks = UserDailyStreak.objects.all().order_by("-streak_count")
            serializer = UserDailyStreakSerializer(streaks, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class UserActivityBadgeAPIView(APIView):
    def get(self, request, user_id=None):
        if user_id:
            # Fetch badges for a specific user
            badges = UserActivityBadge.objects.filter(user__id=user_id)
            serializer = UserActivityBadgeSerializer(badges, many=True)
        else:
            # Fetch all badges
            badges = UserActivityBadge.objects.all()
            serializer = UserActivityBadgeSerializer(badges, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class UserRewardAPIView(APIView):
    def get(self, request, user_id=None):
        if user_id:
            # Fetch rewards for a specific user
            rewards = Reward.objects.filter(user__id=user_id)
            serializer = RewardSerializer(rewards, many=True)
        else:
            # Fetch all rewards
            rewards = Reward.objects.all()
            serializer = RewardSerializer(rewards, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
