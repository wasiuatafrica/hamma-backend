from django.core.management.base import BaseCommand
from prop.utils import get_all_balance_equity_data, get_fixed_balance_equity_data


class Command(BaseCommand):

    def handle(self, *args, **options):
        data = get_fixed_balance_equity_data()
        print(data)
