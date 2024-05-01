from django.core.management.base import BaseCommand
from competition.models import CompetitionCumulativeReturns2, CompetitionDailyReturns2, Competition, CompetitionPortfolio

class Command(BaseCommand):
    help = 'Create or retrieve cumulative and daily returns for competition portfolios.'

    def handle(self, *args, **options):
        competition = Competition.objects.get(status='current')
        portfolios = CompetitionPortfolio.objects.filter(competition=competition)

        for portfolio in portfolios:
            cumulative_return, created_cum = CompetitionCumulativeReturns2.objects.get_or_create(portfolio=portfolio)
            daily_return, created_daily = CompetitionDailyReturns2.objects.get_or_create(portfolio=portfolio)

            if created_cum:
                # If a new cumulative return object was created, you might want to initialize or set default values
                print(f"Created new cumulative return for {portfolio.user}")

            if created_daily:
                # If a new daily return object was created, perform some additional operations
                print(f"Created new daily return for {portfolio.user}")
