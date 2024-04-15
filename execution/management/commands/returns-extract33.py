# Import necessary libraries
import openpyxl
from django.core.management.base import BaseCommand
from execution.models import DemoDailyReturns, DemoCumulativeReturns

class Command(BaseCommand):
    help = 'Export DemoDailyReturns data to xlsx file'

    def handle(self, *args, **kwargs):
        # Query DemoDailyReturns data
        # data = DemoDailyReturns.objects.all()
        data = DemoDailyReturns.objects.filter(user__email='ayo@ft9ja.com', portfolio_returns=47.64)
        print(len(data))
        for dat in data:
            dat.portfolio_returns = 0
            dat.save()
        print('end')
       
        