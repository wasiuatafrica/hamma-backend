from django.core.management.base import BaseCommand
from datetime import datetime
from django.contrib.auth import get_user_model
import competition
from competition.models import Competition
from competition.views import Create_competiton_summary,rank_clans,rank_traders

User =get_user_model()


class Command (BaseCommand):
    help = ''

    def handle (self, *args, **options):
        competition = Competition.objects.get(status='current')
        
        Create_competiton_summary(competition)
        rank_traders(competition)
        rank_clans(competition)