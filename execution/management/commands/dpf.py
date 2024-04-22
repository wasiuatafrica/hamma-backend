import json
from math import e
from django.core.management.base import BaseCommand
from competition.models import get_price
from portfolio.models import Stock
from execution.models import DemoDailyReturns2, DailyReturns, DemoCumulativeReturns
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()



class Command(BaseCommand):
    help = 'Save all Stock symbols as JSON file'

    def handle(self, *args, **options):
        users = User.objects.all()
        for user in users:
            try:
                ret = DemoDailyReturns2.objects.filter(user=user)
                if not ret:
                    raise DemoDailyReturns2.DoesNotExist
            except DemoDailyReturns2.DoesNotExist:
                print(f"{user.email} has no returns")
                
                DemoDailyReturns2.objects.create(user=user, created=timezone.now())
                DailyReturns.objects.create(user=user, created=timezone.now())
                DemoCumulativeReturns.objects.create(user=user, created=timezone.now())
            
            
