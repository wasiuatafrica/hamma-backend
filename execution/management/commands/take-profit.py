import json
from django.core.management.base import BaseCommand
from portfolio.models import Stock
from execution.tasks import calc_stop_loss, calc_tailing_sl, calc_take_profit
class Command(BaseCommand):
    help = 'Save all Stock symbols as JSON file'

    def handle(self, *args, **options):
        calc_take_profit()