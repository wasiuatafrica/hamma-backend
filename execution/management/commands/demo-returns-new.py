from django.core.management.base import BaseCommand
from django.utils import timezone
from execution.models import (
    DemoDailyReturns2,
    DemoPortfolio,
    DemoPosition,
    DemoCumulativeReturns,
)
import pandas as pd
import numpy as np
from tvDatafeed import TvDatafeed, Interval
from execution.utils import days_since_date


def daily_returns5(portfolio):

    positions = DemoPosition.objects.filter(portfolio=portfolio, status="close")

    data = {
        "email": [position.portfolio.user.email for position in positions],
        "Stock": [position.stock.symbol for position in positions],
        "Quantity": [position.quantity for position in positions],
        "Open_Price": [position.open_price for position in positions],
        "Close_Price": [position.close_price for position in positions],
        "Status": [position.get_status_display() for position in positions],
        "closedatetime": [
            timezone.localtime(position.updated).replace(tzinfo=None)
            for position in positions
        ],
        "Amount_Invested": [float(position.amount_invested) for position in positions],
        "Profit_Loss": [float(position.profit_loss) for position in positions],
    }
    df = pd.DataFrame(data)
    print(df)

    df["Balance"] = 1000000
    df["Closedate"] = df["closedatetime"].dt.date

    df = df[
        [
            "Stock",
            "Balance",
            "Amount_Invested",
            "Closedate",
            "closedatetime",
        ]
    ]
    df = df.reset_index(drop=True)
    df = df.sort_values(by="closedatetime")

    df["Sum_Balance"] = df.groupby("Closedate")["Balance"].cumsum()
    df["Sum_Invested"] = df.groupby("Closedate")["Amount_Invested"].cumsum()

    df["Daily_PortfolioReturns"] = ((df["Sum_Balance"] / df["Sum_Invested"]) - 1) * 100

    idx_max_time = df.groupby("Closedate")["closedatetime"].idxmax()

    max_time = (
        df.loc[idx_max_time].reset_index(drop=True).sort_values(by="closedatetime")
    )

    for index, row in max_time.iterrows():
        daily_return = DemoDailyReturns2.objects.filter(
            portfolio=portfolio, created__date=row["Closedate"], first_entry=False
        ).first()
        if daily_return:
            print(daily_return.portfolio_returns, daily_return.created)
            daily_return.portfolio_returns = round(row["Daily_PortfolioReturns"], 2)
            # daily_return.save()

        # daily_return.portfolio_returns = round(row["Daily_PortfolioReturns"], 2)
        # daily_return.save()

    cum_table = max_time[["closedatetime", "Sum_Balance", "Sum_Invested"]]
    cum_table = cum_table.reset_index(drop=True)

    cum_table["running_Balance"] = cum_table["Sum_Balance"].cumsum()
    cum_table["running_Invested"] = cum_table["Sum_Invested"].cumsum()
    cum_table["cum_returns"] = (
        (cum_table.running_Balance / cum_table.running_Invested) - 1
    ) * 100

    for index, row in cum_table.iterrows():
        cum_return = DemoCumulativeReturns.objects.filter(
            portfolio=portfolio,
            created__date=row["closedatetime"].date(),
            first_entry=False,
        ).first()
        if cum_return:
            cum_return.portfolio_returns = round(row["cum_returns"], 2)
            # cum_return.save()

        # cum_return.portfolio_returns = round(row["cum_returns"], 2)
        # cum_return.save()

    tv = TvDatafeed()

    # days_passed = days_since_date('2024-05-1')
    portfolio_creation_date = portfolio.created.date().strftime("%Y-%m-%d")
    days_passed = days_since_date(portfolio_creation_date)
    # print('days',days_passed)
    n_bars = 1 + days_passed
    df2 = tv.get_hist(
        symbol="ASI",
        exchange="NSENG",
        interval=Interval.in_daily,
        n_bars=n_bars,
    )
    ASI_daily_selected = df2.reset_index()
    ASI_daily_selected["ASI_daily_retuns"] = (
        ASI_daily_selected["close"].pct_change() * 100
    )
    ASI_daily_selected["Date"] = ASI_daily_selected["datetime"].dt.strftime("%Y-%m-%d")

    for index, row in ASI_daily_selected.iterrows():
        market_returns = row["ASI_daily_retuns"]
        if np.isnan(market_returns):
            market_returns = 0

        # Update market returns for DemoDailyReturns2
        daily_return = DemoDailyReturns2.objects.filter(
            portfolio=portfolio, created__date=row["Date"]
        ).first()
        if daily_return:
            daily_return.market_returns = round(market_returns, 2)
            # daily_return.save()

    cum_mark_table = ASI_daily_selected[["Date", "ASI_daily_retuns"]]
    cum_mark_table["cum_ASI_daily_retuns"] = (
        1 + cum_mark_table.ASI_daily_retuns / 100
    ).cumprod() - 1
    cum_mark_table["cum_ASI_daily_retuns"] = cum_mark_table.cum_ASI_daily_retuns * 100

    for index, cum_row in cum_mark_table.iterrows():
        cum_market_returns = cum_row["cum_ASI_daily_retuns"]
        if np.isnan(cum_market_returns):
            cum_market_returns = 0

        cum_return = DemoCumulativeReturns.objects.filter(
            portfolio=portfolio, created__date=cum_row["Date"]
        ).first()
        if cum_return:
            cum_return.market_returns = round(cum_market_returns, 2)
            # cum_return.save()


class Command(BaseCommand):
    help = "Recalculate and update portfolio_returns for existing DemoDailyReturns2 records"

    def handle(self, *args, **kwargs):
        # # Fetch all DemoDailyReturns2 records
        # demo_returns = DemoDailyReturns2.objects.all()

        # # Counter for logging
        # updated_count = 0

        # for daily_return in demo_returns:
        #     portfolio = daily_return.portfolio

        #     daily_returns5(portfolio)

        #     updated_count += 1
        #     self.stdout.write(
        #         self.style.SUCCESS(f"Successfully recalculated returns for portfolio: {portfolio.account_name}")
        #     )

        # Log the total number of updated records
        # self.stdout.write(
        #     self.style.SUCCESS(
        #         f"Updated portfolio returns for {updated_count} records."
        #     )
        # )

        portfolio = DemoPortfolio.objects.get(
            user__email="nexxyb@gmail.com", account_name="demo_account_1"
        )

        daily_returns5(portfolio)
