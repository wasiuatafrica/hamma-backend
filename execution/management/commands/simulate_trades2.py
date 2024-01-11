from django.core.management.base import BaseCommand, CommandError
from execution.trades import simulate_trades2
from django.contrib.auth import get_user_model

User= get_user_model()
class Command(BaseCommand):
    help = 'Simulate trades'

    def add_arguments(self, parser):
        parser.add_argument('email', type=str, help='User email to simulate trades for')

    def handle(self, *args, **options):
        user_email = options['email']

        try:
            user = User.objects.get(email=user_email)
            simulate_trades2(user)
        except User.DoesNotExist:
            raise CommandError(f'User with email "{user_email}" does not exist.')
