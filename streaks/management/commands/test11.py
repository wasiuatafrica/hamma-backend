# your_app/management/commands/print_stock_data.py
from django.core.management.base import BaseCommand
from streaks.tasks import (
    update_user_streaks_daily_task,
    award_weekly_badges_and_update_leaderboard,
)


class Command(BaseCommand):
    help = "check alert"

    def handle(self, *args, **options):
        update_user_streaks_daily_task()
