from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from execution.models import DemoPosition
from competition.models import Competition, CompetitionPosition
from datetime import timedelta

from django.db.models import Q

from .models import (
    Leaderboard,
    Reward,
    UserActivityBadge,
    UserDailyStreak,
    UserDailyTradeActivity,
    UserStreakRun,
)
from .serializers import (
    LeaderboardSerializer,
    RewardSerializer,
    UserActivityBadgeSerializer,
    UserDailyStreakSerializer,
    UserStreakRunSerializer,
)
from .tasks import update_user_streaks_daily, award_weekly_badges_and_update_leaderboard
from competition.models import CompetitionPortfolio
from execution.models import DemoPortfolio
from django.contrib.auth import get_user_model

User = get_user_model()
# class LeaderboardAPIView(APIView):
#     def get(self, request):
#         """
#         Get the current week's leaderboard data.
#         """
#         # Get the current week's leaderboard data
#         current_week_start = timezone.now().date() - timezone.timedelta(
#             days=timezone.now().date().weekday()
#         )
#         leaderboard = Leaderboard.objects.filter(
#             week_start_date=current_week_start
#         ).order_by("position")
#         serializer = LeaderboardSerializer(leaderboard, many=True)
#         return Response(serializer.data, status=status.HTTP_200_OK)

# class LeaderboardAPIView(APIView):
#     def get(self, request):
#         """
#         Get the current week's leaderboard data.
#         """
#         today = timezone.now().date()
#         week_start = today - timedelta(days=today.weekday())
#         week_end = week_start + timedelta(days=6)
#         leaderboard_dict =[]
#         for user in User.objects.all():
#         # Calculate the number of trades opened by the user in the past week
#             weekly_open_trades = (
#                 DemoPosition.objects.filter(
#                     portfolio__user=user,
#                     status=DemoPosition.OPEN,
#                     updated__date__range=(week_start, week_end),
#                 ).count()
#                 + CompetitionPosition.objects.filter(
#                     portfolio__user=user,
#                     status=CompetitionPosition.OPEN,
#                     updated__date__range=(week_start, week_end),
#                 ).count()
#             )
#             data = {
#                 "user_id": user.id,
#                 "fullname":user.fullname,
#                 "email":user.email,
#                 "total_trades": weekly_open_trades,
#                 "award":None

#             }
#             leaderboard_dict.append(data)

#         return Response(leaderboard_dict, status=status.HTTP_200_OK)

from operator import itemgetter


class LeaderboardAPIView(APIView):
    def get(self, request):
        """
        Get the current week's leaderboard data.
        Returns weekly awards on Fridays after market close (3 PM).
        """
        today = timezone.now()
        current_time = today.time()
        weekday = today.weekday()
        # Check if we're in the awards period
        is_awards_period = (
            # Friday after 2 PM (weekday 4, hour >= 14)
            (weekday == 4 and current_time.hour >= 14)
            or
            # Saturday (weekday 5) - all day
            (weekday == 5)
            or
            # Sunday (weekday 6) - all day
            (weekday == 6)
            or
            # Monday before 10 AM (weekday 0, hour < 10)
            (weekday == 0 and current_time.hour < 10)
        )

        # If we're in the awards period, return awards data
        if is_awards_period:
            return self.get_weekly_awards()

        # Otherwise return regular leaderboard
        return self.get_regular_leaderboard()

    def get_regular_leaderboard(self):
        """
        Get regular leaderboard data ordered by total trades.
        """
        today = timezone.now().date()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)

        leaderboard_data = []

        for user in User.objects.all():

            # Calculate trades opened by the user in the past week
            demo_trades = DemoPosition.objects.filter(
                portfolio__user=user,
                status__in=[DemoPosition.OPEN, DemoPosition.CLOSED],
                created__date__gte=week_start,
                created__date__lte=week_end,
                updated__date__gte=week_start,
                updated__date__lte=week_end,
            ).count()

            competition_trades = CompetitionPosition.objects.filter(
                portfolio__user=user,
                portfolio__competition__status="current",
                status__in=[CompetitionPosition.OPEN, CompetitionPosition.CLOSED],
                portfolio__active=True,
                created__date__gte=week_start,
                created__date__lte=week_end,
                updated__date__gte=week_start,
                updated__date__lte=week_end,
            ).count()

            trade_volume = demo_trades + competition_trades

            # Only include users who have made trades
            if trade_volume > 0:
                data = {
                    "user": {
                        "id": user.id,
                        "email": user.email,
                        "firstname": user.firstname,
                        "lastname": user.lastname,
                    },
                    "trade_volume": trade_volume,
                    "reward_amount": None,
                    "week_start_date": week_start,
                }
                leaderboard_data.append(data)

        # Sort by trade_volume in descending order
        leaderboard_data.sort(key=itemgetter("trade_volume"), reverse=True)

        # Add position/rank to each entry
        for index, entry in enumerate(leaderboard_data, 1):
            entry["position"] = index
        return Response(leaderboard_data, status=status.HTTP_200_OK)

    def get_weekly_awards(self):
        """
        Get weekly awards data for Friday after market close.
        """
        # Get the current week's leaderboard data
        current_week_start = timezone.now().date() - timezone.timedelta(
            days=timezone.now().date().weekday()
        )
        leaderboard = Leaderboard.objects.filter(
            week_start_date=current_week_start
        ).order_by("position")
        serializer = LeaderboardSerializer(leaderboard, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class LongestStreakAPIView(APIView):
    """
    Get the longest streak achieved by the user.
    """

    def get(self, request):

        account_type = request.GET.get("account_type")
        account_id = request.GET.get("account_id")

        if not (account_id and account_type):
            return Response(
                {"error": "account_id and account_type is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if account_type == "competition_account":
            account = get_object_or_404(CompetitionPortfolio, id=account_id)
            streak_info = get_object_or_404(
                UserDailyStreak, user=request.user, comp_portfolio=account
            )
        elif account_type == "demo_portfolio":
            account = get_object_or_404(DemoPortfolio, id=account_id)
            streak_info = get_object_or_404(
                UserDailyStreak, user=request.user, demo_portfolio=account
            )
        else:
            return Response(
                {"error": "Invalid account type."}, status=status.HTTP_400_BAD_REQUEST
            )
        longest_streak_run = streak_info.longest_streak
        return Response(
            {"longest_streak": longest_streak_run}, status=status.HTTP_200_OK
        )


# class CurrentStreakAPIView(APIView):
#     """
#     Get the details of the current active streak for a user.
#     """

#     def get(self, request):
#         account_type = request.GET.get("account_type")
#         account_id = request.GET.get("account_id")

#         if not (account_id and account_type):
#             return Response(
#                 {"error": "account_id and account_type is required."},
#                 status=status.HTTP_400_BAD_REQUEST,
#             )

#         # Get account and streak info based on account type
#         if account_type == "competition_account":
#             account = get_object_or_404(CompetitionPortfolio, id=account_id)
#             streak_info = UserDailyStreak.objects.filter(
#                 user=request.user,
#                 comp_portfolio=account,
#                 current_streak__gt=0,
#             ).first()
#         elif account_type == "demo_portfolio":
#             account = get_object_or_404(DemoPortfolio, id=account_id)
#             streak_info = UserDailyStreak.objects.filter(
#                 user=request.user,
#                 demo_portfolio=account,
#                 current_streak__gt=0,
#             ).first()
#         else:
#             return Response(
#                 {"error": "Invalid account type."}, status=status.HTTP_400_BAD_REQUEST
#             )
#         if streak_info:
#             serializer = UserDailyStreakSerializer(streak_info)

#             # Calculate date range for this week
#             today = timezone.now().date()
#             start_of_week = today - timedelta(
#                 days=today.weekday()
#             )  # Monday of the current week

#             # Count trades for the specific account this week

#             if account_type == "competition_account":
#                 num_trades = (
#                     CompetitionPosition.objects.filter(portfolio=account)
#                     .filter(
#                         Q(created__date__gte=start_of_week, created__date__lte=today)
#                         & ~Q(status__in=["pending", "cancelled"])
#                         | Q(
#                             status="open",
#                             updated__date__gte=start_of_week,
#                             updated__date__lte=today,
#                             order_type="limit",
#                         )
#                     )
#                     .distinct()
#                     .count()
#                 )
#             else:  # demo_portfolio
#                 num_trades = (
#                     DemoPosition.objects.filter(portfolio=account)
#                     .filter(
#                         Q(created__date__gte=start_of_week, created__date__lte=today)
#                         & ~Q(status__in=["pending", "cancelled"])
#                         | Q(
#                             status="open",
#                             updated__date__gte=start_of_week,
#                             updated__date__lte=today,
#                             order_type="limit",
#                         )
#                     )
#                     .distinct()
#                     .count()
#                 )
#             return Response(
#                 {"streak": serializer.data, "num_of_trades": num_trades},
#                 status=status.HTTP_200_OK,
#             )
#         else:
#             data = {
#                 "streak": {
#                     "user": request.user.id,
#                     "longest_streak_run": 0,
#                     "current_streak_run": {},
#                 },
#                 "num_of_trades": 0,
#             }
#             return Response(data, status=status.HTTP_200_OK)


# class StreakCalendarAPIView(APIView):
#     """
#     Get the calendar view of trading days in the current streak run.
#     """

#     def get(self, request):
#         account_type = request.GET.get("account_type")
#         account_id = request.GET.get("account_id")

#         if not (account_id and account_type):
#             return Response(
#                 {"error": "account_id and account_type is required."},
#                 status=status.HTTP_400_BAD_REQUEST,
#             )

#         if account_type == "competition_account":
#             account = get_object_or_404(CompetitionPortfolio, id=account_id)

#             streak_info = UserDailyStreak.objects.filter(
#                 user=request.user,
#                 comp_portfolio=account,
#                 current_streak__gt=0,
#             ).first()
#         elif account_type == "demo_portfolio":
#             account = get_object_or_404(DemoPortfolio, id=account_id)

#             streak_info = UserDailyStreak.objects.filter(
#                 user=request.user,
#                 demo_portfolio=account,
#                 current_streak__gt=0,
#             ).first()
#         else:
#             return Response(
#                 {"error": "Invalid account type."}, status=status.HTTP_400_BAD_REQUEST
#             )

#         if streak_info:

#             active_streak_run = streak_info.get_active_streak_run()

#             if not active_streak_run:
#                 return Response(
#                     {"error": "No active streak run found for this user."},
#                     status=status.HTTP_404_NOT_FOUND,
#                 )

#             print("Helloooo")

#             # Only include trade dates from the last missed date if any
#             trade_activities = active_streak_run.daily_activities.order_by("trade_date")
#             trade_dates = [activity.trade_date for activity in trade_activities]
#             print(trade_dates)

#             return Response({"trade_dates": trade_dates}, status=status.HTTP_200_OK)
#         else:
#             data = {"trade_dates": []}
#             return Response(data, status=status.HTTP_200_OK)


class CurrentStreakAPIView(APIView):
    """
    Get the details of the current active streak for a user.
    """

    def get(self, request):
        account_type = request.GET.get("account_type")
        account_id = request.GET.get("account_id")

        if not (account_id and account_type):
            return Response(
                {"error": "account_id and account_type is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        today = timezone.now().date()
        start_of_week = today - timedelta(
            days=today.weekday()
        )  # Monday of current week

        # Get account and streak info based on account type
        if account_type == "competition_account":
            account = get_object_or_404(CompetitionPortfolio, id=account_id)
            streak_info = UserDailyStreak.objects.filter(
                user=request.user,
                comp_portfolio=account,
            ).first()
        elif account_type == "demo_portfolio":
            account = get_object_or_404(DemoPortfolio, id=account_id)
            streak_info = UserDailyStreak.objects.filter(
                user=request.user,
                demo_portfolio=account,
            ).first()
        else:
            return Response(
                {"error": "Invalid account type."}, status=status.HTTP_400_BAD_REQUEST
            )

        if streak_info:
            serializer = UserDailyStreakSerializer(streak_info)

            # Count trades for the specific account this week
            if account_type == "competition_account":
                num_trades = (
                    CompetitionPosition.objects.filter(
                        portfolio=account,
                        created__date__gte=start_of_week,
                        created__date__lte=today,
                    )
                    .filter(
                        Q(order_type="market")
                        | Q(
                            status="open",
                            order_type="limit",
                            updated__date__gte=start_of_week,
                        )
                    )
                    .distinct()
                    .count()
                )
            else:  # demo_portfolio
                num_trades = (
                    DemoPosition.objects.filter(
                        portfolio=account,
                        created__date__gte=start_of_week,
                        created__date__lte=today,
                    )
                    .filter(
                        Q(order_type="market")
                        | Q(
                            status="open",
                            order_type="limit",
                            updated__date__gte=start_of_week,
                        )
                    )
                    .distinct()
                    .count()
                )

            return Response(
                {
                    "streak": serializer.data,
                    "num_of_trades": num_trades,
                    "week_start": start_of_week,
                    "week_end": start_of_week + timedelta(days=4),  # Friday
                },
                status=status.HTTP_200_OK,
            )
        else:
            data = {
                "streak": {
                    "user": request.user.id,
                    "longest_streak_run": 0,
                    "current_streak_run": {},
                    "current_week_progress": 0,
                },
                "num_of_trades": 0,
                "week_start": start_of_week,
                "week_end": start_of_week + timedelta(days=4),
            }
            return Response(data, status=status.HTTP_200_OK)


class StreakCalendarAPIView(APIView):
    """
    Get the calendar view of trading days in the current streak run.
    """

    def get(self, request):
        account_type = request.GET.get("account_type")
        account_id = request.GET.get("account_id")

        if not (account_id and account_type):
            return Response(
                {"error": "account_id and account_type is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if account_type == "competition_account":
            account = get_object_or_404(CompetitionPortfolio, id=account_id)
            streak_info = UserDailyStreak.objects.filter(
                user=request.user,
                comp_portfolio=account,
            ).first()
        elif account_type == "demo_portfolio":
            account = get_object_or_404(DemoPortfolio, id=account_id)
            streak_info = UserDailyStreak.objects.filter(
                user=request.user,
                demo_portfolio=account,
            ).first()
        else:
            return Response(
                {"error": "Invalid account type."}, status=status.HTTP_400_BAD_REQUEST
            )

        if streak_info:
            active_streak_run = streak_info.get_active_streak_run()

            if not active_streak_run:
                return Response(
                    {"error": "No active streak run found for this user."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            # Get all consecutive streak runs
            streak_runs = []
            current_run = active_streak_run
            while current_run:
                streak_runs.append(current_run)
                current_run = current_run.previous_streak

            # Collect all trade dates from all consecutive streak runs
            all_trade_dates = []
            for run in streak_runs:
                trade_activities = run.daily_activities.order_by("trade_date")
                all_trade_dates.extend(
                    [activity.trade_date for activity in trade_activities]
                )

            return Response(
                {
                    "trade_dates": all_trade_dates,
                    "current_week_start": streak_info.current_week_start,
                },
                status=status.HTTP_200_OK,
            )
        else:
            data = {"trade_dates": [], "current_week_start": None}
            return Response(data, status=status.HTTP_200_OK)


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
