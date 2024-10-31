from enum import unique
from django.db import models
from django.contrib.auth import get_user_model
from datetime import datetime
import auto_prefetch

from competition.models import CompetitionPortfolio
from execution.models import DemoPortfolio

User = get_user_model()


class DemoPortfolioFieldModel(auto_prefetch.Model):
    """
    Represents a demo portfolio for  users.
    This model is abstract and would be inherited by models which should be connected to demoportfolio or commpetion portfolio
    """

    # Required fields for GenericForeignKey
    demo_portfolio = auto_prefetch.ForeignKey(
        DemoPortfolio, on_delete=models.CASCADE, null=True, blank=True
    )
    comp_portfolio = auto_prefetch.ForeignKey(
        CompetitionPortfolio, on_delete=models.CASCADE, null=True, blank=True
    )

    class Meta(auto_prefetch.Model.Meta):
        """demo portfolios meta class"""

        abstract = True


class UserStreakRun(DemoPortfolioFieldModel):
    """
    Represents a continuous streak of trading days for a user.
    A new streak run is created when a trading day is missed.
    """

    user = auto_prefetch.ForeignKey(
        User, on_delete=models.CASCADE, related_name="streak_runs"
    )
    start_date = models.DateField(auto_now_add=True)
    end_date = models.DateField(null=True, blank=True)  # Marks the end of a streak run
    is_active = models.BooleanField(
        default=True
    )  # True if this streak is currently ongoing

    def end_streak(self):
        """Mark this streak run as ended."""
        self.end_date = datetime.now()
        self.is_active = False
        self.save()

    @property
    def streak_length(self):
        """Calculate the number of days in this streak run."""
        if self.is_active:
            return (datetime.now().date() - self.start_date).days + 1
        elif self.end_date:
            return (self.end_date - self.start_date).days + 1
        return 0

    def __str__(self):
        return f"{self.user.email} - Streak Run from {self.start_date} to {self.end_date or 'Ongoing'}"


class UserDailyTradeActivity(DemoPortfolioFieldModel):
    """
    Represents each trading day activity by the user, attached to an active streak run.
    """

    user = auto_prefetch.ForeignKey(
        User, on_delete=models.CASCADE, related_name="daily_trade_activities"
    )
    streak_run = auto_prefetch.ForeignKey(
        UserStreakRun, on_delete=models.CASCADE, related_name="daily_activities"
    )
    trade_date = models.DateField()

    class Meta(auto_prefetch.Model.Meta):
        # unique_together = ("user", "trade_date")
        constraints = [
            models.UniqueConstraint(
                fields=["demo_portfolio", "trade_date"],
                name="unique_with_demo_portfolio",
            ),
            models.UniqueConstraint(
                fields=["comp_portfolio", "trade_date"],
                name="unique_with_demo_comp_portfolio",
            ),
        ]

    def __str__(self):
        return f"{self.user.email} - Trade on {self.trade_date}"


class UserDailyStreak(DemoPortfolioFieldModel):
    """
    Maintains the current and longest streak for a user.
    """

    user = auto_prefetch.ForeignKey(
        User, on_delete=models.CASCADE, related_name="streak_info"
    )
    current_streak = models.PositiveIntegerField(default=0)
    longest_streak = models.PositiveIntegerField(default=0)

    def update_streak(self, is_new_run=False):
        """Updates current and longest streak based on streak runs."""
        if is_new_run:
            # New streak run, reset current streak to 1
            self.current_streak = 1
        else:
            # Increment the current streak count
            self.current_streak += 1

        # Update longest streak if needed
        if self.current_streak > self.longest_streak:
            self.longest_streak = self.current_streak

        self.save()

    def get_active_streak_run(self):
        """
        Retrieve the current active streak run for this user.
        """
        return (
            UserStreakRun.objects.filter(user=self.user, is_active=True)
            .order_by("-start_date")
            .first()
        )

    def reset_streak(self):
        """Resets the current streak to 0 when a day is missed."""
        self.current_streak = 0
        self.save()

    def __str__(self):
        return f"{self.user.email} - Current Streak: {self.current_streak}, Longest Streak: {self.longest_streak}"


class UserActivityBadge(auto_prefetch.Model):
    user = auto_prefetch.ForeignKey(
        User, on_delete=models.CASCADE, related_name="activity_badges"
    )
    badge_name = models.CharField(
        max_length=50,
        choices=[
            ("Active User", "Active User"),
            ("Key Active User", "Key Active User"),
        ],
    )
    awarded_on = models.DateField()

    def __str__(self):
        return f"{self.user.email} - Badge: {self.badge_name} on {self.awarded_on}"


class Leaderboard(auto_prefetch.Model):
    user = auto_prefetch.ForeignKey(
        User, on_delete=models.CASCADE, related_name="leaderboard_positions"
    )
    position = models.PositiveIntegerField()
    streak_count = models.PositiveIntegerField(default=0)
    trade_volume = models.PositiveIntegerField(default=0)
    week_start_date = models.DateField()
    reward_earned = models.BooleanField(default=False)

    class Meta(auto_prefetch.Model.Meta):
        unique_together = ("user", "week_start_date")

    def __str__(self):
        return (
            f"{self.user.email} - Position: {self.position} Streak: {self.streak_count}"
        )


class Reward(auto_prefetch.Model):
    user = auto_prefetch.ForeignKey(
        User, on_delete=models.CASCADE, related_name="rewards"
    )
    reward_amount = models.DecimalField(max_digits=10, decimal_places=2)
    awarded_on = models.DateField(auto_now_add=True)
    reason = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.user.email} - Reward: {self.reward_amount} for {self.reason}"
