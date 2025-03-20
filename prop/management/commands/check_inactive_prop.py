from django.core.management.base import BaseCommand
from django.utils import timezone
from decimal import Decimal
import logging

from execution.models import DemoPortfolio, DemoPosition
from prop.analyzer import PortfolioAnalyzer

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Test inactivity check for a specific portfolio account"

    def handle(self, *args, **options):
        account_id = str(50157814)

        try:
            # Get the portfolio with the specified account ID
            portfolio = DemoPortfolio.objects.get(account_id=account_id)
            self.stdout.write(self.style.SUCCESS(f"Found portfolio: {portfolio}"))

            # Get the balance/equity data needed for the analyzer
            # This is a simplified example - you'll need to adjust based on your actual data structure
            balance_equity_data = []

            # Get positions to find the timestamps for balance history
            positions = DemoPosition.objects.filter(portfolio=portfolio).order_by(
                "created"
            )

            if positions.exists():
                # Create balance history data points based on positions
                balance = Decimal(str(portfolio.initial_balance))

                for position in positions:
                    # For open positions, use current balance; for closed positions, calculate balance after profit/loss
                    if position.status == "close":
                        profit_loss = position.profit_loss - position.commission
                        balance += Decimal(str(profit_loss))

                    balance_equity_data.append(
                        {
                            "balance": float(balance),
                            "equity": float(
                                balance
                            ),  # For simplicity, using balance as equity
                            "timestamp": position.created.isoformat(),
                        }
                    )

                # Add current balance/equity
                balance_equity_data.append(
                    {
                        "balance": float(portfolio.balance),
                        "equity": float(portfolio.balance),
                        "timestamp": timezone.now().isoformat(),
                    }
                )
            else:
                # If no positions, just use initial and current balance
                balance_equity_data = [
                    {
                        "balance": float(portfolio.initial_balance),
                        "equity": float(portfolio.initial_balance),
                        "timestamp": portfolio.created.isoformat(),
                    },
                    {
                        "balance": float(portfolio.balance),
                        "equity": float(portfolio.balance),
                        "timestamp": timezone.now().isoformat(),
                    },
                ]

            # Create analyzer and check inactivity
            analyzer = PortfolioAnalyzer(balance_equity_data, portfolio)

            is_inactive = analyzer.check_inactivity()

            if is_inactive:
                self.stdout.write(
                    self.style.WARNING(f"Portfolio {account_id} is INACTIVE")
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(f"Portfolio {account_id} is ACTIVE")
                )

        except DemoPortfolio.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f"Portfolio with account ID {account_id} not found")
            )
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error checking inactivity: {e}"))
