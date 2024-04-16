from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from execution.utils import calculate_cumulative_returns, calculate_cumulative_returns_user, daily_returns2, mark_returns
from execution.tasks import cumulative_returns, update_latest_cumulative_returns
from execution.models import DemoPosition, DemoProfitLoss, DemoCumulativeReturns, DemoDailyReturns2

from django.contrib.auth import get_user_model



User= get_user_model()


class Command(BaseCommand):
    help = 'calculate_cumulative_returns'

    def handle(self, *args, **options):
        users = User.objects.all()
        # cumulative_returns = DemoCumulativeReturns.objects.filter(user=user)
        # for cumulative_return in cumulative_returns:
        #     cumulative_return.delete()
        # for user in users:
        #     DemoCumulativeReturns.objects.create(
        #         user=user
                
        #     )
        
        # calculate_cumulative_returns()
        # update_latest_cumulative_returns()
        
        # calculate_cumulative_returns_user(user)
        
        # for user in users:
        #     DemoDailyReturns2.objects.create(user=user, created=user.date_joined)
        #     DemoCumulativeReturns.objects.create(user=user, created=user.date_joined)
            
        # daily_returns2()
        
        mark_returns()