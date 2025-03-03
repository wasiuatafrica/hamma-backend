from decimal import Decimal
from datetime import datetime, timedelta
from typing import List, Dict
from venv import logger
from django.utils import timezone
from celery import shared_task
import logging
from execution.models import DemoPortfolio, DemoPosition
from portfolio.models import DemoTransaction
from .utils import get_account_data
from .utils import sendMail
from django.conf import settings
import requests


logger = logging.getLogger("django")


class PortfolioAnalyzer:
    def __init__(self, balance_equity_data: List[Dict], portfolio):
        self.data = balance_equity_data
        self.portfolio = portfolio
        self.initial_balance = Decimal(str(portfolio.initial_balance))
        self.account_drawdown_limit = Decimal("10")  # 10% account drawdown limit
        self.daily_drawdown_limit = Decimal("5")  # 5% daily drawdown limit
        self.profit_target = portfolio.profit_target
        self.balance_based_drawdown = portfolio.balance_based_drawdown
        self.swap_fee = Decimal("1000.00")  # 500 naira swap fee

    # def check_account_drawdown_violation(self) -> Dict:
    #     """
    #     Check both balance and equity for account drawdown
    #     Only considers values less than initial balance
    #     Returns dict with drawdown info
    #     """
    #     if not self.data:
    #         return {"violated": False, "drawdown_percentage": 0}

    #     max_drawdown_percentage = Decimal("0")

    #     # Check both balance and equity
    #     for entry in self.data:
    #         balance = Decimal(str(entry["balance"]))

    #         if self.balance_based_drawdown:
    #             # Only check balance for drawdown
    #             if balance < self.initial_balance:
    #                 balance_drawdown = (
    #                     (self.initial_balance - balance) / self.initial_balance
    #                 ) * 100
    #                 max_drawdown_percentage = max(
    #                     max_drawdown_percentage, balance_drawdown
    #                 )
    #         else:
    #             equity = Decimal(str(entry["equity"]))

    #             # Only consider values less than initial balance
    #             if balance < self.initial_balance:
    #                 balance_drawdown = (
    #                     (self.initial_balance - balance) / self.initial_balance
    #                 ) * 100
    #                 max_drawdown_percentage = max(
    #                     max_drawdown_percentage, balance_drawdown
    #                 )

    #             if equity < self.initial_balance:
    #                 equity_drawdown = (
    #                     (self.initial_balance - equity) / self.initial_balance
    #                 ) * 100
    #                 max_drawdown_percentage = max(
    #                     max_drawdown_percentage, equity_drawdown
    #                 )

    #     return {
    #         "violated": max_drawdown_percentage > self.account_drawdown_limit,
    #         "drawdown_percentage": max_drawdown_percentage,
    #     }

    # def check_daily_drawdown_violation(self) -> Dict:
    #     """
    #     Check daily drawdown using both balance and equity
    #     Returns dict with violation info
    #     """
    #     if not self.data:
    #         return {"violated": False, "max_daily_drawdown": 0}

    #     daily_data = {}
    #     max_daily_drawdown = Decimal("0")
    #     violation_date = None

    #     for entry in self.data:
    #         date = entry["timestamp"].date()
    #         balance = Decimal(str(entry["balance"]))
    #         # equity = Decimal(str(entry["equity"]))

    #         if date not in daily_data:
    #             daily_data[date] = {
    #                 "start_balance": balance,
    #                 # "start_equity": equity,
    #                 "low_balance": balance,
    #                 # "low_equity": equity,
    #             }
    #         else:
    #             daily_data[date]["low_balance"] = min(
    #                 daily_data[date]["low_balance"], balance
    #             )
    #             # daily_data[date]["low_equity"] = min(
    #             #     daily_data[date]["low_equity"], equity
    #             # )

    #     # Calculate daily drawdowns
    #     for date, values in daily_data.items():
    #         start_value = max(values["start_balance"], values["start_equity"])
    #         low_balance_drawdown = (
    #             (start_value - values["low_balance"]) / start_value
    #         ) * 100
    #         # low_equity_drawdown = (
    #         #     (start_value - values["low_equity"]) / start_value
    #         # ) * 100

    #         # daily_drawdown = max(low_balance_drawdown, low_equity_drawdown)
    #         daily_drawdown = low_balance_drawdown

    #         if daily_drawdown > max_daily_drawdown:
    #             max_daily_drawdown = daily_drawdown
    #             violation_date = date

    #     return {
    #         "violated": max_daily_drawdown > self.daily_drawdown_limit,
    #         "max_daily_drawdown": max_daily_drawdown,
    #         "violation_date": violation_date,
    #     }

    def check_account_drawdown_violation(self, model_type: str) -> Dict:
        """
        Check both balance and equity for account drawdown.
        Considers only values less than the initial balance.

        Args:
            model_type (str): The model type ('model_1' or other).

        Returns:
            dict: Information about drawdown violation.
        """
        # print(self.data)
        if not self.data:
            return {"violated": False, "drawdown_percentage": 0}

        max_drawdown_percentage = Decimal("0")
        max_drawdown_allowed = (
            Decimal("10.0") if model_type == "model_1" else Decimal("6.0")
        )

        # Check both balance and equity
        for entry in self.data:
            balance = Decimal(str(entry["balance"]))

            # Balance-based drawdown check
            if balance < self.initial_balance:
                balance_drawdown = (
                    (self.initial_balance - balance) / self.initial_balance
                ) * 100
                max_drawdown_percentage = max(max_drawdown_percentage, balance_drawdown)

            # Equity-based drawdown check (if applicable)
            if not self.balance_based_drawdown:
                equity = Decimal(str(entry["equity"]))
                if equity < self.initial_balance:
                    equity_drawdown = (
                        (self.initial_balance - equity) / self.initial_balance
                    ) * 100
                    max_drawdown_percentage = max(
                        max_drawdown_percentage, equity_drawdown
                    )
        print("max_drawdown", max_drawdown_percentage)
        # check for drawdown violation to send mail
        violated = max_drawdown_percentage > max_drawdown_allowed

        if violated:
            # update portfolio
            self.portfolio.blown = True
            self.portfolio.save()
            # send daily draw down violation mail
            # check if the screenshot server exists
            # resp = get_screenshot(email="ideafabulous@gmail.com", account_id="33642544")
            resp = get_screenshot(
                email=self.portfolio.user.email, account_id=self.portfolio.account_id
            )
            print("resp", resp)
            if resp["status"]:

                sendMail(
                    "prop/Drawdown.html",
                    "Account Drawdown Violation Alert",
                    [self.portfolio.user.email],
                    {
                        "ddd_limit": max_drawdown_allowed
                        * self.initial_balance,  # daily draw down limit
                        "current_dd": round(
                            max_drawdown_percentage * self.initial_balance, 2
                        ),
                        "exceeded_by": f"{round(max_drawdown_percentage - max_drawdown_allowed,2)}%",
                        "screenshot_url": resp["screenshot_url"],
                        "first_name": self.portfolio.user.firstname,
                    },
                )
        return {
            "violated": violated,
            "drawdown_percentage": float(max_drawdown_percentage),
        }

    def check_daily_drawdown_violation(self, model_type: str) -> Dict:
        """
        Check daily drawdown using balance.
        Args:
            model_type (str): The model type ('model_1' or other).
        Returns:
            dict: Information about drawdown violation.
        """
        if not self.data:
            return {"violated": False, "max_daily_drawdown": 0, "violation_date": None}

        # Get today's date in 'YYYY-MM-DD' format
        today = datetime.now().strftime("%Y-%m-%d")

        # Filter the data for today
        today_data = [
            entry for entry in self.data if entry["timestamp"].startswith(today)
        ]
        if not today_data:
            return {"violated": False, "max_daily_drawdown": 0, "violation_date": None}

        # Extract the list of balance values for today's data
        balances = [Decimal(str(entry["balance"])) for entry in today_data]
        if not balances:
            return {"violated": False, "max_daily_drawdown": 0, "violation_date": None}

        # Get the initial balance (day starting balance)
        initial_balance = balances[0]

        # Calculate the maximum drawdown achieved
        drawdowns = [
            (initial_balance - balance) / initial_balance * 100
            for balance in balances
            if balance < initial_balance
        ]
        max_drawdown_achieved = max(drawdowns, default=Decimal("0"))

        # Calculate the maximum drawdown allowed based on the model type
        max_drawdown_allowed = (
            Decimal("5.0") if model_type == "model_1" else Decimal("3.0")
        )

        # Determine if a violation occurred
        violated = max_drawdown_achieved > max_drawdown_allowed
        if violated:
            # update portfolio
            self.portfolio.blown = True
            self.portfolio.save()
            # send daily draw down violation mail
            # resp = get_screenshot(email="ideafabulous@gmail.com", account_id="33642544")
            resp = get_screenshot(
                email=self.portfolio.user.email, account_id=self.portfolio.account_id
            )
            if resp["status"]:
                sendMail(
                    "prop/Daily_drawdown.html",
                    "Daily Drawdown Violation Alert",
                    [self.portfolio.user.email],
                    {
                        "ddd_limit": max_drawdown_allowed
                        * initial_balance,  # daily draw down limit
                        "current_dd": round(max_drawdown_achieved * initial_balance, 2),
                        "exceeded_by": f"{round(max_drawdown_achieved - max_drawdown_allowed,2)}%",
                        "screenshot_url": resp["screenshot_url"],
                        "first_name": self.portfolio.user.firstname,
                    },
                )

        return {
            "violated": violated,
            "max_daily_drawdown": float(max_drawdown_achieved),
            "violation_date": today if violated else None,
        }

    def check_inactivity(self) -> bool:
        """
        Check if account balance has not changed in 2 weeks
        Returns True if account is inactive, False otherwise
        """
        if not self.data:
            return False

        current_time = datetime.now(timezone.utc)
        two_weeks_ago = current_time - timedelta(days=14)

        # Filter data for last 2 weeks
        recent_data = [
            entry
            for entry in self.data
            if datetime.fromisoformat(entry["timestamp"]).replace(tzinfo=timezone.utc)
            >= two_weeks_ago
        ]

        # if not recent_data:
        #     logger.info(
        #         f"Portfolio {self.portfolio.id} has no data in the last 2 weeks"
        #     )
        #     return False

        # Check if balance has changed in the last 2 weeks
        initial_balance = Decimal(str(recent_data[0]["balance"]))

        for entry in recent_data[1:]:
            current_balance = Decimal(str(entry["balance"]))
            if current_balance != initial_balance:
                logger.info(
                    f"Portfolio {self.portfolio.id} is active: balance changed from {initial_balance} to {current_balance}"
                )
                return False

    # def check_payout_eligibility(self) -> Dict:
    #     """
    #     Check if account is eligible for payout
    #     """
    #     if self.portfolio.blown or self.portfolio.inactive_by_inactivity:
    #         return {"eligible": False, "reason": "Account is blown or inactive"}

    #     # Check trading days
    #     trading_days = set()
    #     previous_balance = None

    #     for entry in self.data:
    #         current_balance = Decimal(str(entry["balance"]))
    #         current_date = entry["timestamp"].date()

    #         if previous_balance is None or current_balance != previous_balance:
    #             trading_days.add(current_date)
    #             previous_balance = current_balance

    #     if len(trading_days) < 6:
    #         return {
    #             "eligible": False,
    #             "reason": f"Insufficient trading days. Required: 6, Current: {len(trading_days)}",
    #         }

    #     # Check profit target
    #     if self.data:
    #         current_balance = Decimal(str(self.data[-1]["balance"]))
    #         profit_percentage = (
    #             (current_balance - self.initial_balance) / self.initial_balance
    #         ) * 100

    #         if profit_percentage < self.profit_target:
    #             return {
    #                 "eligible": False,
    #                 "reason": f"Profit target not met. Required: {self.profit_target}%, Current: {profit_percentage}%",
    #             }

    #     return {
    #         "eligible": True,
    #         "reason": "All conditions met",
    #         "trading_days": len(trading_days),
    #         "profit_percentage": profit_percentage,
    #     }

    def check_payout_eligibility(self) -> Dict:
        """
        Check if account is eligible for payout based on:
        - Not blown or inactive
        - At least 6 total trading days
        - At least 2 trading days in current week
        - Met profit target
        - Target not already met (only check new qualifiers)
        Also calculates time_to_payout when target is met
        """
        # Skip checks if target is already met
        if self.portfolio.target_met:
            return {"eligible": True, "reason": "Target already met"}

        if self.portfolio.blown or self.portfolio.inactive_by_inactivity:
            return {"eligible": False, "reason": "Account is blown or inactive"}

        # Get current week's Monday and Sunday
        current_date = timezone.now().date()
        monday = current_date - timedelta(days=current_date.weekday())
        sunday = monday + timedelta(days=6)

        trading_days = set()
        current_week_trading_days = set()
        previous_balance = None
        current_balance = None
        first_trade_date = None

        for entry in sorted(self.data, key=lambda x: x["timestamp"]):
            current_balance = Decimal(str(entry["balance"]))
            current_date = datetime.fromisoformat(entry["timestamp"]).date()

            # Only count days where balance changed as trading days
            if previous_balance is None or current_balance != previous_balance:
                trading_days.add(current_date)

                # Track first trade date
                if first_trade_date is None:
                    first_trade_date = current_date

                # Check if trade happened in current week
                if monday <= current_date <= sunday:
                    current_week_trading_days.add(current_date)

            previous_balance = current_balance

        positions = self.portfolio.demopositions2.filter(status="open")

        if positions:
            return {
                "eligible": False,
                "reason": "Account has open positions",
                "trading_days": len(trading_days),
                "current_week_trading_days": len(current_week_trading_days),
            }

        # Check total trading days requirement
        if len(trading_days) < 6:
            return {
                "eligible": False,
                "reason": f"Insufficient total trading days. Required: 6, Current: {len(trading_days)}",
                "trading_days": len(trading_days),
                "current_week_trading_days": len(current_week_trading_days),
            }

        # Check current week trading days requirement
        if len(current_week_trading_days) < 2:
            return {
                "eligible": False,
                "reason": f"Insufficient trading days this week. Required: 2, Current: {len(current_week_trading_days)}",
                "trading_days": len(trading_days),
                "current_week_trading_days": len(current_week_trading_days),
            }

        # Check profit target
        profit = 0
        if current_balance:
            profit = current_balance - self.initial_balance

            if profit < self.profit_target:
                return {
                    "eligible": False,
                    "reason": f"Profit target not met. Required: {self.profit_target}, Current: {profit}",
                    "trading_days": len(trading_days),
                    "current_week_trading_days": len(current_week_trading_days),
                    "profit": profit,
                }

        # Calculate weeks to target met
        if first_trade_date:
            days_to_target = (current_date - first_trade_date).days
            weeks_to_target = (days_to_target // 7) + (
                1 if days_to_target % 7 > 0 else 0
            )
        else:
            weeks_to_target = 0

        # All conditions met
        return {
            "eligible": True,
            "reason": "All conditions met",
            "trading_days": len(trading_days),
            "current_week_trading_days": len(current_week_trading_days),
            "profit": profit,
            "trading_dates": sorted(list(trading_days)),
            # "current_week_trading_dates": sorted(list(current_week_trading_dates)),
            "first_trade_date": first_trade_date,
            "weeks_to_target": weeks_to_target,
        }

    def apply_overnight_swap_fees(self):
        """
        Apply overnight swap fees for balance-based drawdown accounts
        """
        if not self.portfolio.balance_based_drawdown:
            print("not balance based")
            return

        current_date = timezone.now().date()

        # Check if we already charged swap fee today
        if (
            self.portfolio.last_swap_charge_date
            and self.portfolio.last_swap_charge_date == current_date
        ):
            return

        # Get open positions that were held overnight
        overnight_positions = DemoPosition.objects.filter(
            portfolio=self.portfolio,
            status=DemoPosition.OPEN,
            # created__date__lt=current_date,
        )
        print("overnight positions", len(overnight_positions))

        total_swap_fee = self.swap_fee * Decimal(str(len(overnight_positions)))

        if total_swap_fee > 0:
            # Update portfolio balance
            self.portfolio.balance -= total_swap_fee
            self.portfolio.last_swap_charge_date = current_date
            self.portfolio.save()

            for position in overnight_positions:
                position.swap_fee += 1000
                position.save()

                print("swap fee applied")

            # Log the swap fee charge
            logger.info(
                f"Applied overnight swap fee of {total_swap_fee} to portfolio {self.portfolio.id} "
                f"for {len(overnight_positions)} positions"
            )

            DemoTransaction.objects.create(
                user=self.portfolio.user,
                transaction_type=f"swap fees deduction for {self.portfolio.account_id}",
                amount=total_swap_fee,
                status="completed",
            )


def analyze_hamma_request_eligibility(portfolio):
    """
    Celery task to analyze and update portfolio status
    """

    # portfolio = DemoPortfolio.objects.get(id=portfolio_id)

    # Get balance and equity data from your data source
    balance_equity_data = get_account_data(portfolio.account_id)
    # print(balance_equity_data)

    analyzer = PortfolioAnalyzer(balance_equity_data, portfolio)

    # Check account drawdown
    account_drawdown = analyzer.check_account_drawdown_violation(portfolio.model_type)

    # Check daily drawdown
    daily_drawdown = analyzer.check_daily_drawdown_violation(portfolio.model_type)

    # Check inactivity
    is_inactive = analyzer.check_inactivity()

    if is_inactive:
        portfolio.active = False
        portfolio.inactive_by_inactivity = is_inactive

    # Check payout eligibility
    print("checking payout eligibility")
    eligibility = analyzer.check_payout_eligibility()
    print(eligibility)

    # Update portfolio status
    portfolio.blown = account_drawdown["violated"] or daily_drawdown["violated"]
    portfolio.target_met = eligibility["eligible"]

    # Save the changes
    portfolio.save()

    return {
        "account_id": portfolio.account_id,
        "portfolio_id": portfolio.id,
        "status_updated": True,
        "blown": portfolio.blown,
        "inactive": portfolio.inactive_by_inactivity,
        "target_met": portfolio.target_met,
        "account_drawdown": account_drawdown["drawdown_percentage"],
        "daily_drawdown": daily_drawdown["max_daily_drawdown"],
        "last_check": timezone.now(),
        "time_to_payout": portfolio.time_to_payout,
        "eligibility_details": eligibility,
    }


def analyze_portfolio_status(portfolio):
    """
    Celery task to analyze and update portfolio status
    """

    # portfolio = DemoPortfolio.objects.get(id=portfolio_id)

    # Get balance and equity data from your data source
    balance_equity_data = get_account_data(portfolio.account_id)
    # print(balance_equity_data)
    was_target_met = portfolio.target_met

    analyzer = PortfolioAnalyzer(balance_equity_data, portfolio)

    analyzer.apply_overnight_swap_fees()

    # Check account drawdown
    account_drawdown = analyzer.check_account_drawdown_violation(portfolio.model_type)

    # Check daily drawdown
    daily_drawdown = analyzer.check_daily_drawdown_violation(portfolio.model_type)

    # Check inactivity
    is_inactive = analyzer.check_inactivity()

    if is_inactive:
        portfolio.active = False
        portfolio.inactive_by_inactivity = is_inactive
        portfolio.can_trade = False

    # Check payout eligibility
    eligibility = analyzer.check_payout_eligibility()
    print(eligibility)

    # Update portfolio status
    portfolio.blown = account_drawdown["violated"] or daily_drawdown["violated"]
    portfolio.target_met = eligibility["eligible"]

    if portfolio.target_met and not was_target_met:
        portfolio.time_to_payout = eligibility.get("weeks_to_target", 0)

    # Save the changes
    portfolio.save()

    return {
        "account_id": portfolio.account_id,
        "portfolio_id": portfolio.id,
        "status_updated": True,
        "blown": portfolio.blown,
        "inactive": portfolio.inactive_by_inactivity,
        "target_met": portfolio.target_met,
        "account_drawdown": account_drawdown["drawdown_percentage"],
        "daily_drawdown": daily_drawdown["max_daily_drawdown"],
        "last_check": timezone.now(),
        "time_to_payout": portfolio.time_to_payout,
        "eligibility_details": eligibility,
    }


def analyze_hamma_portfolio_status(portfolio):
    """
    Celery task to analyze and update portfolio status
    """

    # portfolio = DemoPortfolio.objects.get(id=portfolio_id)

    # Get balance and equity data from your data source
    balance_equity_data = get_account_data(portfolio.account_id)

    analyzer = PortfolioAnalyzer(balance_equity_data, portfolio)

    print("applying swap")

    analyzer.apply_overnight_swap_fees()

    print("swap appplied")

    # Check account drawdown
    account_drawdown = analyzer.check_account_drawdown_violation(portfolio.model_type)

    # Check daily drawdown
    daily_drawdown = analyzer.check_daily_drawdown_violation(portfolio.model_type)

    # Check inactivity
    is_inactive = analyzer.check_inactivity()

    if is_inactive:
        portfolio.active = False
        portfolio.inactive_by_inactivity = is_inactive

    # Update portfolio status
    portfolio.blown = account_drawdown["violated"] or daily_drawdown["violated"]

    portfolio.save()

    return {
        "account_id": portfolio.account_id,
        "portfolio_id": portfolio.id,
        "status_updated": True,
        "blown": portfolio.blown,
        "inactive": portfolio.inactive_by_inactivity,
        "target_met": portfolio.target_met,
        "account_drawdown": account_drawdown["drawdown_percentage"],
        "daily_drawdown": daily_drawdown["max_daily_drawdown"],
        "last_check": timezone.now(),
        "time_to_payout": portfolio.time_to_payout,
    }


def analyze_portfolio_status_after_close(portfolio):
    """
    Celery task to analyze and update portfolio status
    """

    # portfolio = DemoPortfolio.objects.get(id=portfolio_id)

    # Get balance and equity data from your data source
    balance_equity_data = get_account_data(portfolio.account_id)
    # print(balance_equity_data)
    was_target_met = portfolio.target_met

    analyzer = PortfolioAnalyzer(balance_equity_data, portfolio)

    # Check account drawdown
    account_drawdown = analyzer.check_account_drawdown_violation(portfolio.model_type)

    # Check daily drawdown
    daily_drawdown = analyzer.check_daily_drawdown_violation(portfolio.model_type)

    # Check payout eligibility
    eligibility = analyzer.check_payout_eligibility()
    print(eligibility)

    # Update portfolio status
    portfolio.blown = account_drawdown["violated"] or daily_drawdown["violated"]
    portfolio.target_met = eligibility["eligible"]

    if portfolio.target_met and not was_target_met:
        portfolio.time_to_payout = eligibility.get("weeks_to_target", 0)

    # Save the changes
    portfolio.save()

    return {
        "account_id": portfolio.account_id,
        "portfolio_id": portfolio.id,
        "status_updated": True,
        "blown": portfolio.blown,
        "inactive": portfolio.inactive_by_inactivity,
        "target_met": portfolio.target_met,
        "account_drawdown": account_drawdown["drawdown_percentage"],
        "daily_drawdown": daily_drawdown["max_daily_drawdown"],
        "last_check": timezone.now(),
        "time_to_payout": portfolio.time_to_payout,
        "eligibility_details": eligibility,
    }


def get_screenshot(email, account_id):
    """
    Fetches a screenshot URL for the given account ID.

    Args:
        account_id (str): The account ID to get the screenshot for.

    Returns:
        dict: A dictionary containing the status and the screenshot URL or an error message.
    """
    url = settings.SCREENSHOT_URL
    print("Helloo screenshot")
    try:
        # Make a GET request to the screenshot URL
        resp = requests.get(
            f"{url}?email={email}&account_id={account_id}", timeout=1000
        )
        resp.raise_for_status()  # Raise HTTPError for bad responses (4xx and 5xx)

        # Parse the JSON response
        data = resp.json()
        if data.get("success"):
            return {"status": True, "screenshot_url": data.get("url")}
        else:
            return {
                "status": False,
                "message": "Screenshot service returned a failure response.",
            }

    except requests.exceptions.RequestException as e:
        # Handle any request exceptions
        return {"status": False, "message": f"Request failed: {str(e)}"}
    except ValueError:
        # Handle JSON parsing errors
        return {
            "status": False,
            "message": "Invalid JSON response from screenshot service.",
        }
