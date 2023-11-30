import pandas as pd
from django.core.management.base import BaseCommand
from portfolio.models import Stock

class Command(BaseCommand):
    help = 'Import stocks from an XLSX file'

    def handle(self, *args, **options):
        file_path = 'stocks.xlsx'  # Hardcoded file path
        
        try:
            df = pd.read_excel(file_path)
            self.stdout.write(self.style.SUCCESS(f'Successfully loaded data from {file_path}'))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Error loading data from {file_path}: {e}'))
            return

        for _, row in df.iterrows():
            listing_date = None if row['Date Listed'] == '-' else row['Date Listed']
            incorporation_date = None if row['Date Incorporated'] == '-' else row['Date Incorporated']

            Stock.objects.create(
                symbol=row['Ticker'],
                company=row['Company'],
                sector=row['Sector'],
                listing_date=listing_date,
                incorporation_date=incorporation_date
            )

        self.stdout.write(self.style.SUCCESS('Successfully imported stocks'))
