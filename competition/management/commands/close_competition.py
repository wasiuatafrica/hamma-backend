from django.core.management.base import BaseCommand
from datetime import datetime
from django.contrib.auth import get_user_model
from competition.tasks import end_competition
from competition.models import Competition

from django.utils import timezone
User =get_user_model()


class Command (BaseCommand):
    help = ''

    def handle (self, *args, **options):
        competition = Competition.objects.filter(status='current').first()
        print(competition.end_date, competition.id)
        end_competition(competition.id)