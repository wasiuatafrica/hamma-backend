from decimal import Decimal
from datetime import datetime, timedelta
from typing import List, Dict
from venv import logger
from django.utils import timezone
from celery import shared_task
import logging

logger = logging.getLogger("django")


class PortfolioAnalyzer:
    def __init__(self, balance_equity_data: List[Dict], portfolio):
        self.data = balance_equity_data
        self.portfolio = portfolio
        self.initial_balance = Decimal(str(portfolio.initial_balance))
        self.account_drawdown_limit = Decimal("10")  # 10% account drawdown limit
        self.daily_drawdown_limit = Decimal("5")  # 5% daily drawdown limit
        self.profit_target = portfolio.profit_target

    def check_account_drawdown_violation(self) -> Dict:
        """
        Check both balance and equity for account drawdown
        Only considers values less than initial balance
        Returns dict with drawdown info
        """
        if not self.data:
            return {"violated": False, "drawdown_percentage": 0}

        max_drawdown_percentage = Decimal("0")

        # Check both balance and equity
        for entry in self.data:
            balance = Decimal(str(entry["balance"]))
            equity = Decimal(str(entry["equity"]))

            # Only consider values less than initial balance
            if balance < self.initial_balance:
                balance_drawdown = (
                    (self.initial_balance - balance) / self.initial_balance
                ) * 100
                max_drawdown_percentage = max(max_drawdown_percentage, balance_drawdown)

            if equity < self.initial_balance:
                equity_drawdown = (
                    (self.initial_balance - equity) / self.initial_balance
                ) * 100
                max_drawdown_percentage = max(max_drawdown_percentage, equity_drawdown)

        return {
            "violated": max_drawdown_percentage > self.account_drawdown_limit,
            "drawdown_percentage": max_drawdown_percentage,
        }

    def check_daily_drawdown_violation(self) -> Dict:
        """
        Check daily drawdown using both balance and equity
        Returns dict with violation info
        """
        if not self.data:
            return {"violated": False, "max_daily_drawdown": 0}

        daily_data = {}
        max_daily_drawdown = Decimal("0")
        violation_date = None

        for entry in self.data:
            date = entry["timestamp"].date()
            balance = Decimal(str(entry["balance"]))
            equity = Decimal(str(entry["equity"]))

            if date not in daily_data:
                daily_data[date] = {
                    "start_balance": balance,
                    "start_equity": equity,
                    "low_balance": balance,
                    "low_equity": equity,
                }
            else:
                daily_data[date]["low_balance"] = min(
                    daily_data[date]["low_balance"], balance
                )
                daily_data[date]["low_equity"] = min(
                    daily_data[date]["low_equity"], equity
                )

        # Calculate daily drawdowns
        for date, values in daily_data.items():
            start_value = max(values["start_balance"], values["start_equity"])
            low_balance_drawdown = (
                (start_value - values["low_balance"]) / start_value
            ) * 100
            low_equity_drawdown = (
                (start_value - values["low_equity"]) / start_value
            ) * 100

            daily_drawdown = max(low_balance_drawdown, low_equity_drawdown)

            if daily_drawdown > max_daily_drawdown:
                max_daily_drawdown = daily_drawdown
                violation_date = date

        return {
            "violated": max_daily_drawdown > self.daily_drawdown_limit,
            "max_daily_drawdown": max_daily_drawdown,
            "violation_date": violation_date,
        }

    def check_inactivity(self) -> bool:
        """
        Check if account balance has not changed in 2 weeks
        Returns True if account is inactive, False otherwise
        """
        if not self.data:
            return False

        current_time = timezone.now()
        two_weeks_ago = current_time - timedelta(days=14)

        # Filter data for last 2 weeks
        recent_data = [
            entry for entry in self.data if entry["timestamp"] >= two_weeks_ago
        ]

        if not recent_data:
            logger.info(
                f"Portfolio {self.portfolio.id} has no data in the last 2 weeks"
            )
            return True

        # Check if balance has changed in the last 2 weeks
        initial_balance = Decimal(str(recent_data[0]["balance"]))

        for entry in recent_data[1:]:
            current_balance = Decimal(str(entry["balance"]))
            if current_balance != initial_balance:
                logger.info(
                    f"Portfolio {self.portfolio.id} is active: balance changed from {initial_balance} to {current_balance}"
                )
                return False

        logger.info(
            f"Portfolio {self.portfolio.id} is inactive: balance remained at {initial_balance} for 2 weeks"
        )
        return False

    def check_payout_eligibility(self) -> Dict:
        """
        Check if account is eligible for payout
        """
        if self.portfolio.blown or self.portfolio.inactive_by_inactivity:
            return {"eligible": False, "reason": "Account is blown or inactive"}

        # Check trading days
        trading_days = set()
        previous_balance = None

        for entry in self.data:
            current_balance = Decimal(str(entry["balance"]))
            current_date = entry["timestamp"].date()

            if previous_balance is None or current_balance != previous_balance:
                trading_days.add(current_date)
                previous_balance = current_balance

        if len(trading_days) < 6:
            return {
                "eligible": False,
                "reason": f"Insufficient trading days. Required: 6, Current: {len(trading_days)}",
            }

        # Check profit target
        if self.data:
            current_balance = Decimal(str(self.data[-1]["balance"]))
            profit_percentage = (
                (current_balance - self.initial_balance) / self.initial_balance
            ) * 100

            if profit_percentage < self.profit_target:
                return {
                    "eligible": False,
                    "reason": f"Profit target not met. Required: {self.profit_target}%, Current: {profit_percentage}%",
                }

        return {
            "eligible": True,
            "reason": "All conditions met",
            "trading_days": len(trading_days),
            "profit_percentage": profit_percentage,
        }


def analyze_portfolio_status(portfolio):
    """
    Celery task to analyze and update portfolio status
    """
    try:
        # portfolio = DemoPortfolio.objects.get(id=portfolio_id)

        # Get balance and equity data from your data source
        balance_equity_data = []  # Replace with your actual data fetching logic

        analyzer = PortfolioAnalyzer(balance_equity_data, portfolio)

        # Check account drawdown
        account_drawdown = analyzer.check_account_drawdown_violation()

        # Check daily drawdown
        daily_drawdown = analyzer.check_daily_drawdown_violation()

        # Check inactivity
        is_inactive = analyzer.check_inactivity()

        # Check payout eligibility
        eligibility = analyzer.check_payout_eligibility()

        # Update portfolio status
        portfolio.blown = account_drawdown["violated"] or daily_drawdown["violated"]
        portfolio.inactive_by_inactivity = is_inactive
        portfolio.target_met = eligibility["eligible"]

        # Save the changes
        portfolio.save()

        return {
            "portfolio_id": portfolio.id,
            "status_updated": True,
            "blown": portfolio.blown,
            "inactive": portfolio.inactive_by_inactivity,
            "target_met": portfolio.target_met,
            "account_drawdown": account_drawdown["drawdown_percentage"],
            "daily_drawdown": daily_drawdown["max_daily_drawdown"],
            "last_check": timezone.now(),
        }

    # except DemoPortfolio.DoesNotExist:
    #     return {
    #         'portfolio_id': portfolio_id,
    #         'status_updated': False,
    #         'error': 'Portfolio not found'
    #     }
    except Exception as e:
        return {"portfolio_id": portfolio.id, "status_updated": False, "error": str(e)}
