from django.core.management.base import BaseCommand
from prop.utils import get_all_balance_equity_data, get_fixed_balance_equity_data
from prop.tasks import analyze_portfolio_status_task


class Command(BaseCommand):

    def handle(self, *args, **options):
        data = analyze_portfolio_status_task()
        print(data)
