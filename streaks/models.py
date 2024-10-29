from operator import ge
from django.db import models
from django.contrib.auth import get_user_model

from datetime import datetime, timedelta
import auto_prefetch

User = get_user_model()


class UserDailyStreak(auto_prefetch.Model):
    user = auto_prefetch.ForeignKey(
        User, on_delete=models.CASCADE, related_name="daily_streaks"
    )
    streak_count = models.PositiveIntegerField(default=0)
    last_active_date = models.DateField(null=True, blank=True)
    reset_date = models.DateField(null=True, blank=True)

    def increment_streak(self):
        self.streak_count += 1
        self.last_active_date = datetime.now().date()
        self.save()

    def reset_streak(self):
        self.streak_count = 0
        self.reset_date = datetime.now().date()
        self.save()

    def check_and_update_streak(self):
        """Check if there's a gap since the last active day; if yes, reset streak."""
        today = datetime.now().date()
        if self.last_active_date and (today - self.last_active_date).days > 1:
            self.reset_streak()

    def __str__(self):
        return f"{self.user.username} - Streak: {self.streak_count} days"


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
        return f"{self.user.username} - Badge: {self.badge_name} on {self.awarded_on}"


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
        return f"{self.user.username} - Position: {self.position} Streak: {self.streak_count}"


class Reward(auto_prefetch.Model):
    user = auto_prefetch.ForeignKey(
        User, on_delete=models.CASCADE, related_name="rewards"
    )
    reward_amount = models.DecimalField(max_digits=10, decimal_places=2)
    awarded_on = models.DateField(auto_now_add=True)
    reason = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.user.username} - Reward: {self.reward_amount} for {self.reason}"
