# your_app/management/commands/print_stock_data.py
from django.core.management.base import BaseCommand
from portfolio.utils import get_stockdata2
from portfolio.models import Stock
from stock_icons import ICON_LINKS

class Command(BaseCommand):
    help = 'Prints company:symbol dictionary of all stocks'

    def handle(self, *args, **options):
       stocks = Stock.objects.filter(active=True)
       for stock in stocks:
           stock.logo_url = ICON_LINKS[stock.symbol]
           stock.save()
           print(stock.logo_url)