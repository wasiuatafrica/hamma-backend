from django.core.management.base import BaseCommand
from datetime import datetime
from django.contrib.auth import get_user_model

from django.utils import timezone
User =get_user_model()


class Command (BaseCommand):
    help = ''

    def handle (self, *args, **options):
        from competition.utils import count_business_days
        
        start_date = timezone.now()
        end_date = timezone.now() + timezone.timedelta(days=365)

        business_days = count_business_days(start_date, end_date)
        print(business_days)