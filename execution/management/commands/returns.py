import json
from django.core.management.base import BaseCommand
from portfolio.models import Stock
from execution.tasks import daily_returns, cumulative_returns, returns5
class Command(BaseCommand):
    help = 'Save all Stock symbols as JSON file'

    def handle(self, *args, **options):
        returns5() 