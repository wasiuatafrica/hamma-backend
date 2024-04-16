# Import necessary modules
import pandas as pd
from django.core.management.base import BaseCommand
from execution.models import DemoPosition
from django.utils import timezone

class Command(BaseCommand):
    help = 'Export DemoPosition data to Excel'

    def handle(self, *args, **kwargs):
        # Query DemoPosition data
        positions = DemoPosition.objects.filter(status='close')

        # Create a DataFrame from the queryset
        data = {
            'email': [position.portfolio.user.email for position in positions],
            'Stock': [position.stock.symbol for position in positions],
            'Quantity': [position.quantity for position in positions],
            'Open_Price': [position.open_price for position in positions],
            'Close_Price': [position.close_price for position in positions],
            'Status': [position.get_status_display() for position in positions],
            'closedatetime': [timezone.localtime(position.updated).replace(tzinfo=None) for position in positions],
            'Amount_Invested': [position.amount_invested for position in positions],
            
            'Profit_Loss': [position.profit_loss for position in positions],
        }
        df = pd.DataFrame(data)

        # Write DataFrame to Excel
        file_path = 'demo_positions.xlsx'
        df.to_excel(file_path, index=False)

        self.stdout.write(self.style.SUCCESS(f'DemoPosition data exported to {file_path}'))
