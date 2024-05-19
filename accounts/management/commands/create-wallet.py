from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta, datetime
from portfolio.models import Wallet

from django.contrib.auth import get_user_model

User = get_user_model()
class Command (BaseCommand):
    help = ''

    def handle (self, *args, **options):
        
        users= User.objects.all()
        for user in users:
            try:
                wallet = Wallet.objects.get(user=user)  
                print('wallet exists for user', user)
            except Wallet.DoesNotExist:
                wallet = Wallet.objects.create(user=user)
                print('wallet created for user', user)