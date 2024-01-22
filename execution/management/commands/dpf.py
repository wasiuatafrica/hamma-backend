import json
from django.core.management.base import BaseCommand
from portfolio.models import Stock
from execution.tasks import get_daily_profit_loss


class Command(BaseCommand):
    help = 'Save all Stock symbols as JSON file'

    def handle(self, *args, **options):
        get_daily_profit_loss()
