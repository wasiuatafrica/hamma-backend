from django.core.management.base import BaseCommand
from datetime import datetime
from django.contrib.auth import get_user_model

from django.utils import timezone
User =get_user_model()


class Command (BaseCommand):
    help = ''

    def handle (self, *args, **options):
        from competition.tasks import get_top, friday_evening
        
        friday_evening()