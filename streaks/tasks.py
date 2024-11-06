import datetime
import logging
from datetime import time, timedelta

import pytz
from celery import shared_task
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from competition.models import Competition, CompetitionPortfolio, CompetitionPosition
from execution.models import DemoPortfolio, DemoPosition

from .models import (
    Leaderboard,
    Reward,
    UserActivityBadge,
    RewardAmount,
)
from .streak_utils import update_user_streaks_daily

logger = logging.getLogger(__name__)

User = get_user_model()


@shared_task
def update_user_streaks_daily_task():
    # update_user_streaks_daily()
    lagos_timezone = pytz.timezone("Africa/Lagos")
    current_time_lagos = timezone.now().astimezone(lagos_timezone)

    if (
        current_time_lagos.time() >= time(10, 5)
        and current_time_lagos.time() <= time(14, 35)
        and current_time_lagos.weekday() < 5
    ):
        # logger.info("Updating user streaks during trading hours")
        print("Updating user streaks during trading hours")
        update_user_streaks_daily()
    else:
        # logger.info(f"Streak checking is outside trading hours: {current_time_lagos}")
        print(f"Streak checking is outside trading hours: {current_time_lagos}")


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
                status=DemoPosition.OPEN,
                updated__date__range=(week_start, week_end),
            ).count()
            + CompetitionPosition.objects.filter(
                portfolio__user=user,
                status=CompetitionPosition.OPEN,
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
