# your_app/management/commands/print_stock_data.py
from django.core.management.base import BaseCommand
from portfolio.utils import get_stockdata2

class Command(BaseCommand):
    help = 'Prints company:symbol dictionary of all stocks'

    def handle(self, *args, **options):
       data = get_stockdata2()
       print(data)