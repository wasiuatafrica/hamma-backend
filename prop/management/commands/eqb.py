from re import U
from django.core.management.base import BaseCommand
from prop.utils import get_all_balance_equity_data, get_fixed_balance_equity_data
from prop.tasks import analyze_portfolio_status_task, analyze_portfolio_after_close_task
from accounts.tasks import send_prop_welcome_email
from django.contrib.auth import get_user_model
from prop.analyzer import get_screenshot

User = get_user_model()


class Command(BaseCommand):

    def handle(self, *args, **options):
        data = analyze_portfolio_status_task()
        # data = analyze_portfolio_after_close_task("84549103")
        print(data)
        # user = User.objects.get(email="nexxyb@gmail.com")
        # send_prop_welcome_email(user.id)
        # shot = get_screenshot(email="ideafabulous@gmail.com", account_id="33642544")
        # print(shot)

        # get_fixed_balance_equity_data()
