# your_app/management/commands/print_stock_data.py
from django.core.management.base import BaseCommand
from portfolio.models import FeedsCategory
import json

class Command(BaseCommand):
    help = 'Prints company:symbol dictionary of all stocks'

    def handle(self, *args, **options):
        names = [
            "Fundamental Analysis",
            "Price Action",
            "Indicators",
            
        ]
        
        for name in names:
            category = FeedsCategory.objects.create(name=name)
            print(f"Category: {category.name}")