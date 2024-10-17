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
    df["closedatetime"] = pd.to_datetime(df["closedatetime"], errors="coerce")
    df["Balance"] = 1000000
    df["Closedate"] = df["closedatetime"].dt.date
    df = df[
        [
            "Stock",
            "Balance",
            "Amount_Invested",
            "Closedate",
            "closedatetime",
            "Profit_Loss",
        ]
    ]
    df = df.reset_index(drop=True)
    df = df.sort_values(by="closedatetime")
    df["Sum_Profit_Loss"] = df.groupby("Closedate")["Profit_Loss"].cumsum()
    df["Daily_PortfolioReturns"] = df["Sum_Profit_Loss"] / df["Balance"] * 100
    # print(df)

    df_final = df.groupby("Closedate").tail(1).reset_index(drop=True)

    print(df_final)

    for index, row in df_final.iterrows():
        daily_return = DemoDailyReturns2.objects.filter(
            portfolio=portfolio, created__date=row["Closedate"], first_entry=False
        ).first()
        if daily_return:
            print(row["Closedate"])
            print(daily_return.portfolio_returns, daily_return.created.date())
            daily_return.portfolio_returns = round(row["Daily_PortfolioReturns"], 2)
            daily_return.save()

    cum_table = df_final[["closedatetime", "Sum_Profit_Loss", "Balance"]]
    cum_table = cum_table.reset_index(drop=True)
    cum_table["running_pl"] = cum_table["Sum_Profit_Loss"].cumsum()
    cum_table["cum_returns"] = (cum_table.running_pl / cum_table.Balance) * 100

    print(cum_table)

    for index, row in cum_table.iterrows():
        cum_return = DemoCumulativeReturns.objects.filter(
            portfolio=portfolio,
            created__date=row["closedatetime"].date(),
            first_entry=False,
        ).first()
        if cum_return:
            cum_return.portfolio_returns = round(row["cum_returns"], 2)
            cum_return.save()

    print("returns calculated")


class Command(BaseCommand):
    help = "Recalculate and update portfolio_returns for existing DemoDailyReturns2 records"

    def handle(self, *args, **kwargs):
        # Fetch all DemoDailyReturns2 records
        demo_portfolios = DemoPortfolio.objects.all()

        # Counter for logging
        updated_count = 0

        for portfolio in demo_portfolios:

            daily_returns5(portfolio)

            updated_count += 1
            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully recalculated returns for portfolio: {portfolio.account_name}"
                )
            )

        # Log the total number of updated records
        self.stdout.write(
            self.style.SUCCESS(
                f"Updated portfolio returns for {updated_count} records."
            )
        )

        # portfolio = DemoPortfolio.objects.get(
        #     user__email="kolapoay@gmail.com",
        #     account_name="DA",
        #     # user__email="nexxyb@gmail.com",
        #     # account_name="demo_account_1",
        # )

        # daily_returns5(portfolio)
