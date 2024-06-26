from django.core.management.base import BaseCommand
from datetime import datetime
from django.contrib.auth import get_user_model
import competition
from competition.models import Competition, CompetitionPosition, CompetitionPortfolio
from competition.views import Create_competiton_summary,rank_clans,rank_traders
import portfolio

User =get_user_model()


class Command (BaseCommand):
    help = ''

    def handle (self, *args, **options):
        competition = Competition.objects.filter(status='closed').last()
        # open_positions = CompetitionPosition.objects.filter(portfolio__competition=competition, status='close')
        # print(len(open_positions))
        # Create_competiton_summary(competition)
        # rank_traders(competition)
        rank_clans(competition)