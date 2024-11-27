from django.db import transaction
from datetime import timedelta
from decimal import Decimal
from django.utils import timezone
from .models import Payout
from execution.models import DemoPosition
from .utils import get_equity_balance


class PayoutService:
    def __init__(self, portfolio):
        self.portfolio = portfolio
        self.current_time = timezone.now()

    def check_payout_eligibility(self):
        """Check all conditions that must be met for payout eligibility"""
        conditions = {
            "minimum_trading_days": self._check_minimum_trading_days(),
            "profit_target_met": self._check_profit_target(),
            "drawdown_limits": self._check_drawdown_limits(),
            "minimum_trades": self._check_minimum_trades(),
            "active_account": self._check_account_active(),
            "payout_timing": self._check_payout_timing(),
            "no_open_trades": self._check_no_open_trades(),
        }

        return all(conditions.values()), conditions

    def _check_no_open_trades(self):
        """Check if there are any open trades"""
        open_trades_count = DemoPosition.objects.filter(
            portfolio=self.portfolio, status="open"
        ).count()
        return open_trades_count == 0

    def _check_minimum_trading_days(self):
        # Check if there are at least 2 trading days in the current week
        week_start = self.current_time - timedelta(days=self.current_time.weekday())
        trading_days = (
            DemoPosition.objects.filter(
                portfolio=self.portfolio, created__gte=week_start, status="close"
            )
            .dates("created", "day")
            .count()
        )

        return trading_days >= 2

    def _check_profit_target(self):
        current_data = get_equity_balance(self.portfolio)
        profit = Decimal(str(current_data["equity"])) - self.portfolio.initial_balance
        return profit > 0

    def _check_drawdown_limits(self):
        # Check if account is within drawdown limits
        current_data = get_equity_balance(self.portfolio)
        return not self.portfolio.blown

    def _check_minimum_trades(self):
        # Check if minimum number of trades requirement is met
        week_start = self.current_time - timedelta(days=self.current_time.weekday())
        trades_count = DemoPosition.objects.filter(
            portfolio=self.portfolio, created__gte=week_start, status="close"
        ).count()
        return trades_count > 0

    def _check_account_active(self):
        return (
            self.portfolio.is_active
            and not self.portfolio.blown
            and not self.portfolio.inactive_by_inactivity
        )

    def _check_payout_timing(self):
        current_weekday = self.current_time.weekday()

        # Check if it's Wednesday (2), Thursday (3), or Friday (4)
        is_valid_day = current_weekday in [2, 3, 4]

        # For Friday, check if time is before 12 PM (noon)
        if current_weekday == 4:  # Friday
            return is_valid_day and self.current_time.hour < 12

        # For Wednesday and Thursday, allow all times
        return is_valid_day

    # def calculate_payout_amount(self):
    #     """Calculate the payout amount based on profit and time period"""
    #     current_data = get_equity_balance(self.portfolio)
    #     profit = Decimal(str(current_data["equity"])) - self.portfolio.initial_balance

    #     # Calculate weeks since account creation
    #     weeks_active = (self.current_time - self.portfolio.created).days // 7

    #     # Determine profit split percentage based on weeks active
    #     if weeks_active <= 4:
    #         split_percentage = Decimal("0.90")  # 90%
    #     elif weeks_active <= 12:
    #         split_percentage = Decimal("0.60")  # 60%
    #     else:
    #         split_percentage = Decimal("0.40")  # 40%

    #     payout_amount = profit * split_percentage
    #     return payout_amount, split_percentage

    @transaction.atomic
    def process_payout_request(self):
        """Process the payout request and create a Payout record"""
        # is_eligible, conditions = self.check_payout_eligibility()

        # if not is_eligible:
        #     failed_conditions = [k for k, v in conditions.items() if not v]
        #     raise ValueError(
        #         f"Payout conditions not met: {', '.join(failed_conditions)}"
        #     )

        # amount, split_percentage = self.calculate_payout_amount()

        # if amount <= 0:
        #     raise ValueError("No profit available for payout")

        payout = Payout.objects.create(
            portfolio=self.portfolio,
            # amount=amount,
            # profit_percentage=split_percentage * 100,
            amount=0,
            profit_percentage=0,
            week_number=(self.current_time - self.portfolio.created).days // 7,
            status="pending",
        )

        return payout
