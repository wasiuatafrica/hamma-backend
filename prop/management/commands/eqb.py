from re import U
from django.core.management.base import BaseCommand
from prop.utils import get_all_balance_equity_data, get_fixed_balance_equity_data
from prop.tasks import analyze_portfolio_status_task
from accounts.tasks import send_prop_welcome_email
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):

    def handle(self, *args, **options):
        data = analyze_portfolio_status_task()
        print(data)
        # user = User.objects.get(email="nexxyb@gmail.com")
        # send_prop_welcome_email(user.id)
