from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from execution.models import DemoPortfolio, DemoPosition
from execution.views2 import EnhancedPortfolioCalculator
from prop.utils import db_prop


class Command(BaseCommand):
    help = "Calculate and store fixed balance/equity data for a single account by account_id."

    def handle(self, *args, **options):
        account_id = 24116067
        try:
            account = DemoPortfolio.objects.get(
                account_id=account_id,
            )
        except DemoPortfolio.DoesNotExist:
            raise CommandError(
                f"No active prop account found with account_id: {account_id}"
            )

        calculator = EnhancedPortfolioCalculator()
        positions = DemoPosition.objects.filter(portfolio=account)
        account_data = calculator.calculate_portfolio_metrics(account, positions)
        mongo_data = {
            "balance": float(account_data["balance"]),
            "equity": float(account_data["equity"]),
            "timestamp": timezone.now().strftime("%Y-%m-%dT%H:%M"),
            "account_id": account.account_id,
        }
        self.stdout.write(str(mongo_data))
        self.stdout.write(
            self.style.SUCCESS(f"Inserted data for account_id: {account.account_id}")
        )
