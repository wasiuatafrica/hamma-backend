# your_app/management/commands/print_stock_data.py
from django.core.management.base import BaseCommand
from portfolio.models import Stock
import json

class Command(BaseCommand):
    help = 'Prints company:symbol dictionary of all stocks'

    def handle(self, *args, **options):
        stocks_data = Stock.objects.values('company', 'symbol')
        stocks_dict = {stock['company']: stock['symbol'] for stock in stocks_data}

        stocks_json = json.dumps(stocks_dict, indent=2)

        self.stdout.write(self.style.SUCCESS("Stocks Dictionary (JSON format):"))
        self.stdout.write(stocks_json)