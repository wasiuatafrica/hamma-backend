from django.core.management.base import BaseCommand
from competition.models import CompetitionCumulativeReturns2, CompetitionDailyReturns2, Competition, CompetitionPortfolio
from django.utils import timezone

class Command(BaseCommand):
    help = 'Create or retrieve cumulative and daily returns for competition portfolios.'

    def handle(self, *args, **options):
        competition = Competition.objects.get(status='current')
        portfolios = CompetitionPortfolio.objects.filter(competition=competition)

        for portfolio in portfolios:
            CompetitionDailyReturns2 .objects.create(portfolio=portfolio,created=timezone.now())
            CompetitionCumulativeReturns2.objects.create(portfolio=portfolio, created=timezone.now())
