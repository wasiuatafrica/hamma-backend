from django.core.management.base import BaseCommand
from execution.utils import calculate_cumulative_returns
from execution.tasks import update_latest_cumulative_returns
from execution.models import DemoPosition, DemoProfitLoss, DemoCumulativeReturns

from django.contrib.auth import get_user_model



User= get_user_model()


class Command(BaseCommand):
    help = 'calculate_cumulative_returns'

    def handle(self, *args, **options):
        # users = User.objects.all()
        # for user in users:
        #     DemoCumulativeReturns.objects.create(
        #         user=user
                
        #     )
        
        # calculate_cumulative_returns()
        update_latest_cumulative_returns()