from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from portfolio.models import Stock
from execution.history import get_data, save_to_mongo



User= get_user_model()
class Command(BaseCommand):
    help = 'get historical data'

    def handle(self, *args, **options):
        stocks = [stock.symbol for stock in Stock.objects.all()]
        for symbol in stocks:
            data = get_data(symbol)
            print(data.head())
            save_to_mongo(symbol, data[:10])