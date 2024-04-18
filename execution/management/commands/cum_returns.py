from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from execution.utils import calculate_cumulative_returns, calculate_cumulative_returns_user, daily_returns2, mark_returns, daily_returns3
from execution.tasks import cumulative_returns, update_latest_cumulative_returns
from execution.models import DemoPosition, DemoProfitLoss, DemoCumulativeReturns, DemoDailyReturns2

from django.contrib.auth import get_user_model



User= get_user_model()


class Command(BaseCommand):
    help = 'calculate_cumulative_returns'

    def handle(self, *args, **options):
        # users = User.objects.all()
        
        
        # for user in users:
        #     DemoDailyReturns2.objects.create(user=user, created=user.date_joined)
        #     DemoCumulativeReturns.objects.create(user=user, created=user.date_joined)
            
        # daily_returns2()
        
        mark_returns()
        # daily_returns3()