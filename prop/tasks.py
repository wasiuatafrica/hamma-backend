from celery.app import shared_task
from .utils import get_all_balance_equity_data, get_fixed_balance_equity_data
from .analyzer import analyze_portfolio_status
from execution.models import DemoPortfolio


@shared_task
def get_all_balance_equity_data_task():
    get_all_balance_equity_data()


@shared_task
def get_current_prop_data_task():
    get_fixed_balance_equity_data()


@shared_task
def analyze_portfolio_status_task():
    portfolios = DemoPortfolio.objects.filter(
        is_prop=True,
        blown=False,
        inactive_by_inactivity=False,
        activated=True,
    )
    for portfolio in portfolios:
        if portfolio.account_type_level == "challenge":
            data = analyze_portfolio_status(portfolio)
            print(data)
