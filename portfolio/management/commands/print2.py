# your_app/management/commands/print_stock_data.py
from django.core.management.base import BaseCommand
from portfolio.utils import get_stockdata2
from portfolio.models import Stock
from stock_icons2 import ICON_LINKS

class Command(BaseCommand):
    help = 'Prints company:symbol dictionary of all stocks'

    def handle(self, *args, **options):
        stocks = Stock.objects.filter(active=True)
        for stock in stocks:
            url = ICON_LINKS.get(stock.symbol)
            if url:
                stock.logo_url = url
                stock.save()
                print(stock.logo_url)
            else:
                print(f"No link for {stock.symbol}")
            