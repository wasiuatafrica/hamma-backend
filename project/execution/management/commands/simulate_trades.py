from django.core.management.base import BaseCommand
from execution.trades import simulate_trades
from django.contrib.auth import get_user_model

User= get_user_model()
class Command(BaseCommand):
    help = 'Simulate trades'

    def handle(self, *args, **options):
        users = User.objects.all()
        for user in users:
            simulate_trades(user)