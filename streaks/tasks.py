import datetime
import json
import logging
from datetime import time, timedelta

import pytz
from celery import shared_task
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from portfolio.market_hours import is_trading_time
from django_celery_beat.models import IntervalSchedule, PeriodicTask

from competition.models import Competition, CompetitionPortfolio, CompetitionPosition
from execution.models import DemoPortfolio, DemoPosition

from .models import Leaderboard, Reward, RewardAmount, UserActivityBadge
from .serializers import LeaderboardSerializer
from .streak_utils import update_user_streaks_daily

logger = logging.getLogger(__name__)

User = get_user_model()


@shared_task
def update_user_streaks_daily_task():
    # update_user_streaks_daily()
    lagos_timezone = pytz.timezone("Africa/Lagos")
    current_time_lagos = timezone.now().astimezone(
        lagos_timezone
    )  # - timedelta(days=2)

    if is_trading_time(current_time_lagos, start_offset=5, end_offset=10):
        # logger.info("Updating user streaks during trading hours")
        update_user_streaks_daily()

    else:
        # logger.info(f"Streak checking is outside trading hours: {current_time_lagos}")
        pass


default_position_awards = [
    {"type": "Top Leaderboard Reward", "position": 1, "reward_amount": 25000},
    {"type": "Top Leaderboard Reward", "position": 2, "reward_amount": 15000},
    {"type": "Top Leaderboard Reward", "position": 3, "reward_amount": 10000},
    {"type": "Top Leaderboard Reward", "position": 4, "reward_amount": 5000},
    {"type": "Top Leaderboard Reward", "position": 5, "reward_amount": 3000},
    {"type": "Key active user", "position": 0, "reward_amount": 1000},
]


@shared_task
def award_weekly_badges_and_update_leaderboard():
    """
    Weekly task to award badges and update the leaderboard based on weekly trading activity.
    """
    today = timezone.now().date()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)

    for user in User.objects.all():
        # Calculate the number of trades opened by the user in the past week
        weekly_open_trades = (
            DemoPosition.objects.filter(
                portfolio__user=user,
                status__in=[DemoPosition.OPEN, DemoPosition.CLOSED],
                updated__date__range=(week_start, week_end),
            ).count()
            + CompetitionPosition.objects.filter(
                portfolio__user=user,
                status__in=[CompetitionPosition.OPEN, CompetitionPosition.CLOSED],
                updated__date__range=(week_start, week_end),
            ).count()
        )

        # Award badges based on weekly trade count
        if weekly_open_trades >= 10:
            UserActivityBadge.objects.get_or_create(
                user=user, badge_name="Key Active User", awarded_on=week_start
            )
        elif weekly_open_trades >= 3:
            UserActivityBadge.objects.get_or_create(
                user=user, badge_name="Active User", awarded_on=week_start
            )

        # Update or create leaderboard entry for the user based on trade volume not streak
        leaderboard_entry, _ = Leaderboard.objects.get_or_create(
            user=user, week_start_date=week_start, position=0
        )
        leaderboard_entry.trade_volume = weekly_open_trades
        # leaderboard_entry.streak_count = (
        #     UserDailyStreak.objects.filter(user=user).first().current_streak or 0
        # )
        leaderboard_entry.save()

    # Rank users by streak count and trade volume for leaderboard positions
    # leaderboard = Leaderboard.objects.filter(week_start_date=week_start).order_by(
    #     "-streak_count", "-trade_volume"
    # )
    # Rank users by trade volume for leaderboard positions
    leaderboard = Leaderboard.objects.filter(week_start_date=week_start).order_by(
        "-trade_volume"
    )

    for position, entry in enumerate(leaderboard, start=1):
        entry.position = position
        entry.save()

    # Award rewards to the top 5 users based on their leaderboard ranking
    index = 0
    for entry in leaderboard[:5]:
        reward = RewardAmount.objects.filter(
            position=entry.position, reward_type="leaderboard"
        ).first()
        reward_amount = (
            reward.reward_amount
            if reward
            else default_position_awards[index]["reward_amount"]
        )
        index += 1
        if not entry.reward_earned:
            Reward.objects.create(
                user=entry.user,
                reward_amount=reward_amount,
                reason="Top Leaderboard Reward",
            )
            entry.reward_earned = True
            entry.save()

    # Award additional reward to users with the "Key Active User" badge for the week
    key_active_users = UserActivityBadge.objects.filter(
        badge_name="Key Active User", awarded_on=week_start
    )
    for badge in key_active_users:
        reward = RewardAmount.objects.filter(reward_type="key_active_user").first()
        reward_amount = (
            reward.reward_amount
            if reward
            else default_position_awards[5]["reward_amount"]
        )
        Reward.objects.create(
            user=badge.user,
            reward_amount=reward_amount,
            reason="Key Active User Reward",
        )


@shared_task
def cache_regular_leaderboard():
    """
    Cache regular leaderboard data for 1 hour.

    """
    today = timezone.now().date()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)

    leaderboard_data = []
    for user in User.objects.all():
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
        if trade_volume > 0:
            data = {
                "user": {
                    "firstname": user.firstname,
                    "lastname": user.lastname,
                },
                "trade_volume": trade_volume,
                "reward_amount": None,
                "week_start_date": week_start,
            }
            leaderboard_data.append(data)

    # Sort leaderboard by trade volume
    leaderboard_data.sort(key=lambda x: x["trade_volume"], reverse=True)

    # Add position/rank
    for index, entry in enumerate(leaderboard_data, 1):
        entry["position"] = index

    # Cache the result for 10 minutes
    cache.set("regular_leaderboard", leaderboard_data)

    interval, created = IntervalSchedule.objects.get_or_create(
        every=10,
        period=IntervalSchedule.MINUTES,
    )

    PeriodicTask.objects.create(
        interval=interval,  # set to every 10 minutes
        name="Cache Regular Leaderboard",
        task="streaks.tasks.cache_regular_leaderboard",
        kwargs=json.dumps({}),
    )


@shared_task
def cache_weekly_awards():
    """
    Get weekly awards data for Friday after market close.
    """
    current_week_start = timezone.now().date() - timedelta(
        days=timezone.now().date().weekday()
    )
    leaderboard = Leaderboard.objects.filter(
        week_start_date=current_week_start
    ).order_by("position")
    serializer = LeaderboardSerializer(leaderboard, many=True)

    # Cache the result for 10 minutes
    cache.set("weekly_awards", serializer.data)

    # Set up interval schedule (every 10 minutes)
    interval, created = IntervalSchedule.objects.get_or_create(
        every=10,
        period=IntervalSchedule.MINUTES,
    )

    PeriodicTask.objects.create(
        interval=interval,  # set to every 10 minutes
        name="Cache Weekly Awards",
        task="streaks.tasks.cache_weekly_awards",
        kwargs=json.dumps({}),
    )
