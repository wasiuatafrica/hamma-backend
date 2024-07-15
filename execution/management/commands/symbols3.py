import json
from django.core.management.base import BaseCommand
from portfolio.models import Stock


class Command(BaseCommand):
    help = 'Save all Stock symbols as JSON file'

    def handle(self, *args, **options):
        # Get all Stock objects
        stocks = Stock.objects.filter(active=False).order_by('symbol')

        # Create a list of symbols
        symbols = [stock.symbol for stock in stocks]

        # Define the output JSON file path
        output_file_path = 'symbols3.json'

        # Write symbols to JSON file
        with open(output_file_path, 'w') as json_file:
            json.dump(symbols, json_file)

        self.stdout.write(self.style.SUCCESS(f'Successfully saved Stock symbols to {output_file_path}'))
