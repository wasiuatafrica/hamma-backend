from calendar import c
from re import M

from competition.models import (
    Competition,
    CompetitionCumulativeReturns2,
    CompetitionDailyReturns2,
    CompetitionPortfolio,
    CompetitionPosition,
)
from .models import (
    CompetitionCumulativeMarketReturns,
    CompetitionMarketReturns,
    DemoPosition,
    DemoPortfolio,
    DemoCumulativeReturns,
    DemoDailyReturns,
    DemoDailyReturns2,
    MarketReturns,
    CumulativeMarketReturns,
)
from rest_framework import serializers
import pandas as pd
import pytz
from datetime import datetime, timedelta

from anyon.views import User


class DemoPositionSerializer(serializers.ModelSerializer):
    symbol = serializers.SerializerMethodField()

    class Meta:
        model = DemoPosition
        fields = [
            "id",
            "quantity",
            "open_price",
            "close_price",
            "limit_price",
            "status",
            "created",
            "updated",
            "amount_invested",
            "action",
            "time_in_force",
            "order_type",
            "profit_loss",
            "symbol",
        ]

    def get_symbol(self, obj):
        return obj.stock.symbol


def get_positions(user, status=None):
    portfolio = DemoPortfolio.objects.get(user=user)
    if status == "all" or status == None:
        positions = DemoPosition.objects.filter(portfolio=portfolio)
    else:
        positions = DemoPosition.objects.filter(portfolio=portfolio, status=status)

    serializer = DemoPositionSerializer(positions, many=True)
    return serializer.data


def calculate_cumulative_returns():
    """
    Calculates the cumulative returns for each day in the DailyReturns table
    and stores the results in the CumulativeReturns model.
    """
    users = User.objects.all()
    returns = DemoDailyReturns.objects.all().order_by("created")

    for user in users:

        daily_returns = returns.filter(user=user)

        if daily_returns.exists():
            data = {
                "portfolio_returns": [
                    dr.portfolio_returns / 100 for dr in daily_returns
                ],
                "market_returns": [dr.market_returns / 100 for dr in daily_returns],
                "ngx_price": [dr.ngx_price for dr in daily_returns],
                "user": [dr.user for dr in daily_returns],
                "created": [dr.created for dr in daily_returns],
            }
            df = pd.DataFrame(data)

            print(df)

            df["portfolio_cumulative"] = (
                (1 + df["portfolio_returns"]).cumprod() - 1
            ) * 100
            df["market_cumulative"] = ((1 + df["market_returns"]).cumprod() - 1) * 100

            print(df)
            for index, row in df.iterrows():
                DemoCumulativeReturns.objects.create(
                    user=user,
                    portfolio_returns=round(row["portfolio_cumulative"], 2),
                    market_returns=round(row["market_cumulative"], 2),
                    ngx_price=row["ngx_price"],
                    created=row["created"],
                )
        else:
            DemoCumulativeReturns.objects.create(user=user)


def calculate_cumulative_returns_user(user):
    """
    Calculates the cumulative returns for each day in the DailyReturns table
    and stores the results in the CumulativeReturns model.
    """

    daily_returns = DemoDailyReturns.objects.filter(user=user)

    if daily_returns.exists():
        data = {
            "portfolio_returns": [dr.portfolio_returns / 100 for dr in daily_returns],
            "market_returns": [dr.market_returns / 100 for dr in daily_returns],
            "ngx_price": [dr.ngx_price for dr in daily_returns],
            "user": [dr.user for dr in daily_returns],
            "created": [dr.created for dr in daily_returns],
        }
        df = pd.DataFrame(data)

        # print(df)

        df["portfolio_cumulative"] = ((1 + df["portfolio_returns"]).cumprod() - 1) * 100
        df["market_cumulative"] = ((1 + df["market_returns"]).cumprod() - 1) * 100

        print(df)
        for index, row in df.iterrows():
            DemoCumulativeReturns.objects.create(
                user=user,
                portfolio_returns=round(row["portfolio_cumulative"], 2),
                market_returns=round(row["market_cumulative"], 2),
                ngx_price=row["ngx_price"],
                created=row["created"],
            )


from django.utils import timezone


def daily_returns2():
    users = User.objects.all()
    for user in users:
        print(user)
        positions = DemoPosition.objects.filter(portfolio__user=user, status="close")
        if positions.exists():

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
                "Amount_Invested": [
                    float(position.amount_invested) for position in positions
                ],
                "Profit_Loss": [float(position.profit_loss) for position in positions],
            }
            df = pd.DataFrame(data)

            df["Balance"] = df["Amount_Invested"] + df["Profit_Loss"]
            df["Closedate"] = df["closedatetime"].dt.date

            df = df[
                ["Stock", "Balance", "Amount_Invested", "Closedate", "closedatetime"]
            ]
            df = df.reset_index(drop=True)
            df = df.sort_values(by="closedatetime")

            df["Sum_Balance"] = df.groupby("Closedate")["Balance"].cumsum()
            df["Sum_Invested"] = df.groupby("Closedate")["Amount_Invested"].cumsum()

            df["Daily_PortfolioReturns"] = (
                (df["Sum_Balance"] / df["Sum_Invested"]) - 1
            ) * 100

            idx_max_time = df.groupby("Closedate")["closedatetime"].idxmax()

            max_time = (
                df.loc[idx_max_time]
                .reset_index(drop=True)
                .sort_values(by="closedatetime")
            )

            # print(max_time)

            for index, row in max_time.iterrows():
                # print(row['Daily_PortfolioReturns'], row['closedatetime'])
                DemoDailyReturns2.objects.create(
                    user=user,
                    portfolio_returns=round(row["Daily_PortfolioReturns"], 2),
                    created=row["closedatetime"],
                )

            cum_table = max_time[["closedatetime", "Sum_Balance", "Sum_Invested"]]
            cum_table = cum_table.reset_index(drop=True)

            cum_table["running_Balance"] = cum_table["Sum_Balance"].cumsum()
            cum_table["running_Invested"] = cum_table["Sum_Invested"].cumsum()
            cum_table["cum_returns"] = (
                (cum_table.running_Balance / cum_table.running_Invested) - 1
            ) * 100

            # print(cum_table)

            for index, row in cum_table.iterrows():

                DemoCumulativeReturns.objects.create(
                    user=user,
                    portfolio_returns=round(row["cum_returns"], 2),
                    created=row["closedatetime"],
                )
        print("done")


import numpy as np


def mark_returns():
    from tvDatafeed import TvDatafeed, Interval

    tv = TvDatafeed()
    df = tv.get_hist(
        symbol="ASI", exchange="NSENG", interval=Interval.in_daily, n_bars=67
    )
    ASI_daily_selected = df.reset_index()
    ASI_daily_selected["ASI_daily_retuns"] = (
        ASI_daily_selected["close"].pct_change() * 100
    )
    ASI_daily_selected["Date"] = ASI_daily_selected["datetime"].dt.strftime("%Y-%m-%d")

    for index, row in ASI_daily_selected.iterrows():
        print(row["Date"], row["ASI_daily_retuns"])
        market_returns = row["ASI_daily_retuns"]
        if np.isnan(market_returns):
            market_returns = 0  # or any other valid value
        MarketReturns.objects.create(
            market_returns=round(market_returns, 2), created=row["datetime"]
        )

    cum_mark_table = ASI_daily_selected[["Date", "ASI_daily_retuns"]]
    cum_mark_table["cum_ASI_daily_retuns"] = (
        1 + cum_mark_table.ASI_daily_retuns / 100
    ).cumprod() - 1
    cum_mark_table["cum_ASI_daily_retuns"] = cum_mark_table.cum_ASI_daily_retuns * 100

    for index, row in cum_mark_table.iterrows():
        print(row["Date"], row["cum_ASI_daily_retuns"])
        cum_market_returns = row["cum_ASI_daily_retuns"]
        if np.isnan(cum_market_returns):
            cum_market_returns = 0  # or any other valid value
        CumulativeMarketReturns.objects.create(
            market_returns=round(cum_market_returns, 2), created=row["Date"]
        )
    # print(ASI_daily_selected)


def days_since_date(date_str):
    """
    Calculates the number of days that have passed since the given date.

    Args:
        date_str (str): The date in the format 'YYYY-MM-DD'.

    Returns:
        int: The number of days that have passed since the given date.
    """
    today = datetime.now().date()
    date = datetime.strptime(date_str, "%Y-%m-%d").date()
    days_passed = (today - date).days
    return days_passed


def daily_returns3():
    from tvDatafeed import TvDatafeed, Interval

    today = timezone.now().date()

    users = User.objects.all()
    for user in users:
        # print(user)
        positions_today = DemoPosition.objects.filter(
            portfolio__user=user, status="close", updated__date=today
        )
        if positions_today.exists():
            positions = DemoPosition.objects.filter(
                portfolio__user=user, status="close"
            )

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
                "Amount_Invested": [
                    float(position.amount_invested) for position in positions
                ],
                "Profit_Loss": [float(position.profit_loss) for position in positions],
            }
            df = pd.DataFrame(data)

            df["Balance"] = df["Amount_Invested"] + df["Profit_Loss"]
            df["Closedate"] = df["closedatetime"].dt.date

            df = df[
                ["Stock", "Balance", "Amount_Invested", "Closedate", "closedatetime"]
            ]
            df = df.reset_index(drop=True)
            df = df.sort_values(by="closedatetime")

            df["Sum_Balance"] = df.groupby("Closedate")["Balance"].cumsum()
            df["Sum_Invested"] = df.groupby("Closedate")["Amount_Invested"].cumsum()

            df["Daily_PortfolioReturns"] = (
                (df["Sum_Balance"] / df["Sum_Invested"]) - 1
            ) * 100

            idx_max_time = df.groupby("Closedate")["closedatetime"].idxmax()

            max_time = (
                df.loc[idx_max_time]
                .reset_index(drop=True)
                .sort_values(by="closedatetime")
            )

            # Save the last row to the database
            last_row = max_time.iloc[-1]
            DemoDailyReturns2.objects.create(
                user=user,
                portfolio_returns=round(last_row["Daily_PortfolioReturns"], 2),
                created=timezone.now(),
            )

            # Save the last row of the cumulative table to the database
            cum_table = max_time[["closedatetime", "Sum_Balance", "Sum_Invested"]]
            cum_table = cum_table.reset_index(drop=True)

            cum_table["running_Balance"] = cum_table["Sum_Balance"].cumsum()
            cum_table["running_Invested"] = cum_table["Sum_Invested"].cumsum()
            cum_table["cum_returns"] = (
                (cum_table.running_Balance / cum_table.running_Invested) - 1
            ) * 100

            last_row_cum = cum_table.iloc[-1]
            DemoCumulativeReturns.objects.create(
                user=user,
                portfolio_returns=round(last_row_cum["cum_returns"], 2),
                created=timezone.now(),
            )

    tv = TvDatafeed()

    days_passed = days_since_date("2024-04-16")
    # print('days',days_passed)
    n_bars = 65 + days_passed
    df2 = tv.get_hist(
        symbol="ASI", exchange="NSENG", interval=Interval.in_daily, n_bars=n_bars
    )
    ASI_daily_selected = df2.reset_index()
    ASI_daily_selected["ASI_daily_retuns"] = (
        ASI_daily_selected["close"].pct_change() * 100
    )
    ASI_daily_selected["Date"] = ASI_daily_selected["datetime"].dt.strftime("%Y-%m-%d")

    # Save the last row to the database
    last_row_market = ASI_daily_selected.iloc[-1]
    # print(last_row_market)

    market_returns = last_row_market["ASI_daily_retuns"]
    if np.isnan(market_returns):
        market_returns = 0
    MarketReturns.objects.create(
        market_returns=round(market_returns, 2), created=timezone.now()
    )

    cum_mark_table = ASI_daily_selected[["Date", "ASI_daily_retuns"]]
    cum_mark_table["cum_ASI_daily_retuns"] = (
        1 + cum_mark_table.ASI_daily_retuns / 100
    ).cumprod() - 1
    cum_mark_table["cum_ASI_daily_retuns"] = cum_mark_table.cum_ASI_daily_retuns * 100

    # print(cum_mark_table)
    # Save the last row to the database
    last_row_cum_market = cum_mark_table.iloc[-1]
    # print(last_row_cum_market)
    cum_market_returns = last_row_cum_market["cum_ASI_daily_retuns"]
    if np.isnan(cum_market_returns):
        cum_market_returns = 0
    CumulativeMarketReturns.objects.create(
        market_returns=round(cum_market_returns, 2), created=timezone.now()
    )


def competition_daily_returns3():
    from tvDatafeed import TvDatafeed, Interval

    today = timezone.now().date()

    portfolios = CompetitionPortfolio.objects.filter(
        competition__status="current", active=True
    )
    for portfolio in portfolios:
        # print(user)
        positions_today = CompetitionPosition.objects.filter(
            portfolio=portfolio, status="close", updated__date=today
        )

        if positions_today.exists():
            positions = CompetitionPosition.objects.filter(
                portfolio=portfolio, status="close"
            )

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
                "Amount_Invested": [
                    float(position.amount_invested) for position in positions
                ],
                "Profit_Loss": [float(position.profit_loss) for position in positions],
            }
            df = pd.DataFrame(data)

            df["Balance"] = df["Amount_Invested"] + df["Profit_Loss"]
            df["Closedate"] = df["closedatetime"].dt.date

            df = df[
                ["Stock", "Balance", "Amount_Invested", "Closedate", "closedatetime"]
            ]
            df = df.reset_index(drop=True)
            df = df.sort_values(by="closedatetime")

            df["Sum_Balance"] = df.groupby("Closedate")["Balance"].cumsum()
            df["Sum_Invested"] = df.groupby("Closedate")["Amount_Invested"].cumsum()

            df["Daily_PortfolioReturns"] = (
                (df["Sum_Balance"] / df["Sum_Invested"]) - 1
            ) * 100

            idx_max_time = df.groupby("Closedate")["closedatetime"].idxmax()

            max_time = (
                df.loc[idx_max_time]
                .reset_index(drop=True)
                .sort_values(by="closedatetime")
            )

            # Save the last row to the database
            last_row = max_time.iloc[-1]
            CompetitionDailyReturns2.objects.create(
                # user=portfolio.user,
                portfolio=portfolio,
                portfolio_returns=round(last_row["Daily_PortfolioReturns"], 2),
                created=timezone.now(),
            )

            # Save the last row of the cumulative table to the database
            cum_table = max_time[["closedatetime", "Sum_Balance", "Sum_Invested"]]
            cum_table = cum_table.reset_index(drop=True)

            cum_table["running_Balance"] = cum_table["Sum_Balance"].cumsum()
            cum_table["running_Invested"] = cum_table["Sum_Invested"].cumsum()
            cum_table["cum_returns"] = (
                (cum_table.running_Balance / cum_table.running_Invested) - 1
            ) * 100

            last_row_cum = cum_table.iloc[-1]
            CompetitionCumulativeReturns2.objects.create(
                # user=portfolio.user,
                portfolio=portfolio,
                portfolio_returns=round(last_row_cum["cum_returns"], 2),
                created=timezone.now(),
            )


def competition_daily_returns4():
    from tvDatafeed import TvDatafeed, Interval

    today = timezone.now().date()

    lagos_timezone = pytz.timezone("Africa/Lagos")
    current_time_lagos = timezone.now().astimezone(lagos_timezone)
    # print(current_time_lagos)
    if (
        current_time_lagos.time() >= datetime.strptime("10:02 AM", "%I:%M %p").time()
        and current_time_lagos.time() <= datetime.strptime("2:31 PM", "%I:%M %p").time()
        and current_time_lagos.weekday() < 5
    ):

        portfolios = CompetitionPortfolio.objects.filter(
            competition__status="current", active=True
        )
        for portfolio in portfolios:
            # print(user)
            positions_today = CompetitionPosition.objects.filter(
                portfolio=portfolio, status="close", updated__date=today
            )

            if positions_today.exists():
                positions = CompetitionPosition.objects.filter(
                    portfolio=portfolio, status="close"
                )

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
                    "Amount_Invested": [
                        float(position.amount_invested) for position in positions
                    ],
                    "Profit_Loss": [
                        float(position.profit_loss) for position in positions
                    ],
                }
                df = pd.DataFrame(data)

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
                df["Daily_PortfolioReturns"] = (
                    df["Sum_Profit_Loss"] / df["Balance"] * 100
                )
                # print(df)

                df_final = df.groupby("Closedate").tail(1).reset_index(drop=True)
                # print(df_final)

                # Save the last row to the database
                last_row = df_final.iloc[-1]
                d_returns = CompetitionDailyReturns2.objects.filter(
                    # user=portfolio.user,
                    portfolio=portfolio,
                    created__date=timezone.now().date(),
                    first_entry=False,
                ).order_by("-created")

                if d_returns.exists():
                    if len(d_returns) > 1:
                        d_returns = d_returns.order_by("-created")[1]
                    d_returns = d_returns.first()
                    d_returns.portfolio_returns = round(
                        last_row["Daily_PortfolioReturns"], 2
                    )
                    d_returns.created = timezone.now()
                    d_returns.save()
                else:
                    CompetitionDailyReturns2.objects.create(
                        # user=portfolio.user,
                        portfolio=portfolio,
                        portfolio_returns=round(last_row["Daily_PortfolioReturns"], 2),
                        created=timezone.now(),
                        first_entry=False,
                    )

                cum_table = df_final[["closedatetime", "Sum_Profit_Loss", "Balance"]]
                cum_table = cum_table.reset_index(drop=True)
                cum_table["running_pl"] = cum_table["Sum_Profit_Loss"].cumsum()
                cum_table["cum_returns"] = (
                    cum_table.running_pl / cum_table.Balance
                ) * 100

                print(cum_table)
                last_row_cum = cum_table.iloc[-1]

                c_returns = CompetitionCumulativeReturns2.objects.filter(
                    portfolio=portfolio,
                    created__date=timezone.now().date(),
                    first_entry=False,
                )

                if c_returns.exists():
                    c_returns = c_returns.first()
                    c_returns.portfolio_returns = round(last_row_cum["cum_returns"], 2)
                    c_returns.created = timezone.now()
                    c_returns.save()
                else:
                    CompetitionCumulativeReturns2.objects.create(
                        # user=portfolio.user,
                        portfolio=portfolio,
                        portfolio_returns=round(last_row_cum["cum_returns"], 2),
                        created=timezone.now(),
                        first_entry=False,
                    )

        tv = TvDatafeed()

        days_passed = days_since_date("2024-07-15")
        # print('days',days_passed)
        n_bars = 1 + days_passed
        df2 = tv.get_hist(
            symbol="ASI", exchange="NSENG", interval=Interval.in_daily, n_bars=n_bars
        )
        ASI_daily_selected = df2.reset_index()
        ASI_daily_selected["ASI_daily_retuns"] = (
            ASI_daily_selected["close"].pct_change() * 100
        )
        ASI_daily_selected["Date"] = ASI_daily_selected["datetime"].dt.strftime(
            "%Y-%m-%d"
        )

        print(ASI_daily_selected)
        # # Save the last row to the database
        last_row_market = ASI_daily_selected.iloc[-1]
        # # print(last_row_market)

        market_returns = last_row_market["ASI_daily_retuns"]
        if np.isnan(market_returns):
            market_returns = 0

        comp_market = CompetitionMarketReturns.objects.filter(
            created__date=timezone.now().date()
        )
        if comp_market.exists():
            comp_market2 = comp_market.first()
        else:
            comp_market2 = CompetitionMarketReturns.objects.create(
                created=timezone.now()
            )

        comp_market2.market_returns = round(market_returns, 2)
        comp_market2.save()

        cum_mark_table = ASI_daily_selected[["Date", "ASI_daily_retuns"]]
        cum_mark_table["cum_ASI_daily_retuns"] = (
            1 + cum_mark_table.ASI_daily_retuns / 100
        ).cumprod() - 1
        cum_mark_table["cum_ASI_daily_retuns"] = (
            cum_mark_table.cum_ASI_daily_retuns * 100
        )

        # print(cum_mark_table)
        last_row_cum_market = cum_mark_table.iloc[-1]
        # print(last_row_cum_market)
        cum_market_returns = last_row_cum_market["cum_ASI_daily_retuns"]
        if np.isnan(cum_market_returns):
            cum_market_returns = 0
        comp_market_cum = CompetitionCumulativeMarketReturns.objects.filter(
            created__date=timezone.now().date()
        )
        if comp_market_cum.exists():
            comp_market_cum2 = comp_market_cum.first()
        else:
            comp_market_cum2 = CompetitionCumulativeMarketReturns.objects.create(
                created=timezone.now()
            )

        comp_market_cum2.market_returns = round(cum_market_returns, 2)
        comp_market_cum2.save()

        print("all calculated")


def daily_returns5():
    from tvDatafeed import TvDatafeed, Interval

    today = timezone.now().date()

    lagos_timezone = pytz.timezone("Africa/Lagos")
    current_time_lagos = timezone.now().astimezone(lagos_timezone)
    # print(current_time_lagos)

    if (
        current_time_lagos.time() >= datetime.strptime("10:02 AM", "%I:%M %p").time()
        and current_time_lagos.time() <= datetime.strptime("2:31 PM", "%I:%M %p").time()
        and current_time_lagos.weekday() < 5
    ):
        # if current_time_lagos.time() >= datetime.strptime('7:02 AM', '%I:%M %p').time() and current_time_lagos.time() <= datetime.strptime('2:30 PM', '%I:%M %p').time() and current_time_lagos.weekday() < 5:
        users = User.objects.all()
        for user in users:
            portfolios = DemoPortfolio.objects.filter(user=user)
            for portfolio in portfolios:
                # print(user)
                positions_today = DemoPosition.objects.filter(
                    portfolio=portfolio, status="close", updated__date=today
                )

                if positions_today.exists():
                    # print(f"{user} closed position today")
                    positions = DemoPosition.objects.filter(
                        portfolio=portfolio, status="close"
                    )

                    data = {
                        "email": [
                            position.portfolio.user.email for position in positions
                        ],
                        "Stock": [position.stock.symbol for position in positions],
                        "Quantity": [position.quantity for position in positions],
                        "Open_Price": [position.open_price for position in positions],
                        "Close_Price": [position.close_price for position in positions],
                        "Status": [
                            position.get_status_display() for position in positions
                        ],
                        "closedatetime": [
                            timezone.localtime(position.updated).replace(tzinfo=None)
                            for position in positions
                        ],
                        "Amount_Invested": [
                            float(position.amount_invested) for position in positions
                        ],
                        "Profit_Loss": [
                            float(position.profit_loss) for position in positions
                        ],
                    }
                    df = pd.DataFrame(data)

                    df["Balance"] = df["Amount_Invested"] + df["Profit_Loss"]
                    # df["Balance"] = 1000000
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
                    df["Sum_Invested"] = df.groupby("Closedate")[
                        "Amount_Invested"
                    ].cumsum()

                    df["Daily_PortfolioReturns"] = (
                        (df["Sum_Balance"] / df["Sum_Invested"]) - 1
                    ) * 100

                    idx_max_time = df.groupby("Closedate")["closedatetime"].idxmax()

                    max_time = (
                        df.loc[idx_max_time]
                        .reset_index(drop=True)
                        .sort_values(by="closedatetime")
                    )

                    # Save the last row to the database
                    last_row = max_time.iloc[-1]

                    d_returns = DemoDailyReturns2.objects.filter(
                        # user=portfolio.user,
                        portfolio=portfolio,
                        created__date=timezone.now().date(),
                        first_entry=False,
                    ).order_by("-created")

                    if d_returns.exists():
                        # print('daily returns exist today')
                        if len(d_returns) > 1:
                            d_returns = d_returns.order_by("-created")[1]
                        d_returns = d_returns.first()
                        d_returns.portfolio_returns = round(
                            last_row["Daily_PortfolioReturns"], 2
                        )
                        d_returns.created = timezone.now()
                        d_returns.save()
                    else:
                        print("daily returns created first time today")

                        d_returns = DemoDailyReturns2.objects.create(
                            user=portfolio.user,
                            portfolio=portfolio,
                            portfolio_returns=round(
                                last_row["Daily_PortfolioReturns"], 2
                            ),
                            created=timezone.now(),
                            first_entry=False,
                        )

                    cum_table = max_time[
                        ["closedatetime", "Sum_Balance", "Sum_Invested"]
                    ]
                    cum_table = cum_table.reset_index(drop=True)

                    cum_table["running_Balance"] = cum_table["Sum_Balance"].cumsum()
                    cum_table["running_Invested"] = cum_table["Sum_Invested"].cumsum()
                    cum_table["cum_returns"] = (
                        (cum_table.running_Balance / cum_table.running_Invested) - 1
                    ) * 100

                    last_row_cum = cum_table.iloc[-1]

                    c_returns = DemoCumulativeReturns.objects.filter(
                        portfolio=portfolio,
                        created__date=timezone.now().date(),
                        first_entry=False,
                    )

                    if c_returns.exists():
                        c_returns = c_returns.first()
                        c_returns.portfolio_returns = round(
                            last_row_cum["cum_returns"], 2
                        )
                        c_returns.created = timezone.now()
                        c_returns.save()
                    else:
                        c_returns = DemoCumulativeReturns.objects.create(
                            user=portfolio.user,
                            portfolio=portfolio,
                            portfolio_returns=round(last_row_cum["cum_returns"], 2),
                            created=timezone.now(),
                            first_entry=False,
                        )

                    tv = TvDatafeed()

                    # days_passed = days_since_date('2024-05-1')
                    portfolio_creation_date = portfolio.created.date().strftime(
                        "%Y-%m-%d"
                    )
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
                    ASI_daily_selected["Date"] = ASI_daily_selected[
                        "datetime"
                    ].dt.strftime("%Y-%m-%d")

                    # print(ASI_daily_selected)
                    # # Save the last row to the database
                    last_row_market = ASI_daily_selected.iloc[-1]
                    # # print(last_row_market)

                    market_returns = last_row_market["ASI_daily_retuns"]
                    if np.isnan(market_returns):
                        market_returns = 0

                    d_returns.market_returns = round(market_returns, 2)
                    d_returns.save()

                    cum_mark_table = ASI_daily_selected[["Date", "ASI_daily_retuns"]]
                    cum_mark_table["cum_ASI_daily_retuns"] = (
                        1 + cum_mark_table.ASI_daily_retuns / 100
                    ).cumprod() - 1
                    cum_mark_table["cum_ASI_daily_retuns"] = (
                        cum_mark_table.cum_ASI_daily_retuns * 100
                    )

                    # print(cum_mark_table)
                    last_row_cum_market = cum_mark_table.iloc[-1]
                    # print(last_row_cum_market)
                    cum_market_returns = last_row_cum_market["cum_ASI_daily_retuns"]
                    if np.isnan(cum_market_returns):
                        cum_market_returns = 0

                    c_returns.market_returns = round(cum_market_returns, 2)
                    c_returns.save()

        print("all demo returns calculated")


def competition_daily_returns7():
    from tvDatafeed import TvDatafeed, Interval

    today = timezone.now().date()

    lagos_timezone = pytz.timezone("Africa/Lagos")
    current_time_lagos = timezone.now().astimezone(lagos_timezone)
    # print(current_time_lagos)

    # if current_time_lagos.time() >= datetime.strptime('8:02 AM', '%I:%M %p').time() and current_time_lagos.time() <= datetime.strptime('11:31 PM', '%I:%M %p').time() and current_time_lagos.weekday() < 5:
    if (
        current_time_lagos.time() >= datetime.strptime("10:02 AM", "%I:%M %p").time()
        and current_time_lagos.time() <= datetime.strptime("2:30 PM", "%I:%M %p").time()
        and current_time_lagos.weekday() < 5
    ):

        portfolios = CompetitionPortfolio.objects.filter(
            active=True, competition__status="current"
        )
        for portfolio in portfolios:
            positions_today = CompetitionPosition.objects.filter(
                portfolio=portfolio, status="close", updated__date=today
            )

            if positions_today.exists():
                print(f"{portfolio.user} closed position today")
                positions = CompetitionPosition.objects.filter(
                    portfolio=portfolio, status="close"
                )

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
                    "Amount_Invested": [
                        float(position.amount_invested) for position in positions
                    ],
                    "Profit_Loss": [
                        float(position.profit_loss) for position in positions
                    ],
                }
                df = pd.DataFrame(data)

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
                df["Daily_PortfolioReturns"] = (
                    df["Sum_Profit_Loss"] / df["Balance"] * 100
                )
                # print(df)

                df_final = df.groupby("Closedate").tail(1).reset_index(drop=True)
                # print(df_final)

                # Save the last row to the database
                last_row = df_final.iloc[-1]
                d_returns = CompetitionDailyReturns2.objects.filter(
                    # user=portfolio.user,
                    portfolio=portfolio,
                    created__date=timezone.now().date(),
                    first_entry=False,
                ).order_by("-created")

                if d_returns.exists():
                    if len(d_returns) > 1:
                        d_returns = d_returns.order_by("-created")[1]
                    d_returns = d_returns.first()
                    d_returns.portfolio_returns = round(
                        last_row["Daily_PortfolioReturns"], 2
                    )
                    d_returns.created = timezone.now()
                    d_returns.save()
                else:
                    CompetitionDailyReturns2.objects.create(
                        # user=portfolio.user,
                        portfolio=portfolio,
                        portfolio_returns=round(last_row["Daily_PortfolioReturns"], 2),
                        created=timezone.now(),
                        first_entry=False,
                    )

                cum_table = df_final[["closedatetime", "Sum_Profit_Loss", "Balance"]]
                cum_table = cum_table.reset_index(drop=True)
                cum_table["running_pl"] = cum_table["Sum_Profit_Loss"].cumsum()
                cum_table["cum_returns"] = (
                    cum_table.running_pl / cum_table.Balance
                ) * 100

                print(cum_table)
                last_row_cum = cum_table.iloc[-1]

                c_returns = CompetitionCumulativeReturns2.objects.filter(
                    portfolio=portfolio,
                    created__date=timezone.now().date(),
                    first_entry=False,
                )

                if c_returns.exists():
                    c_returns = c_returns.first()
                    c_returns.portfolio_returns = round(last_row_cum["cum_returns"], 2)
                    c_returns.created = timezone.now()
                    c_returns.save()
                else:
                    CompetitionCumulativeReturns2.objects.create(
                        # user=portfolio.user,
                        portfolio=portfolio,
                        portfolio_returns=round(last_row_cum["cum_returns"], 2),
                        created=timezone.now(),
                        first_entry=False,
                    )

                tv = TvDatafeed()

                # days_passed = days_since_date('2024-05-1')
                comparison_date = "2024-07-15"
                portfolio_creation_date = portfolio.created.date().strftime("%Y-%m-%d")
                if portfolio_creation_date < comparison_date:
                    days_passed = days_since_date(comparison_date)
                else:
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
                ASI_daily_selected["Date"] = ASI_daily_selected["datetime"].dt.strftime(
                    "%Y-%m-%d"
                )

                # print(ASI_daily_selected)
                # # Save the last row to the database
                last_row_market = ASI_daily_selected.iloc[-1]
                # print(last_row_market)

                market_returns = last_row_market["ASI_daily_retuns"]
                if np.isnan(market_returns):
                    market_returns = 0

                d_returns.market_returns = round(market_returns, 2)
                d_returns.save()

                cum_mark_table = ASI_daily_selected[["Date", "ASI_daily_retuns"]]
                cum_mark_table["cum_ASI_daily_retuns"] = (
                    1 + cum_mark_table.ASI_daily_retuns / 100
                ).cumprod() - 1
                cum_mark_table["cum_ASI_daily_retuns"] = (
                    cum_mark_table.cum_ASI_daily_retuns * 100
                )

                # print(cum_mark_table)
                last_row_cum_market = cum_mark_table.iloc[-1]
                # print(last_row_cum_market)
                cum_market_returns = last_row_cum_market["cum_ASI_daily_retuns"]
                if np.isnan(cum_market_returns):
                    cum_market_returns = 0

                c_returns.market_returns = round(cum_market_returns, 2)
                c_returns.save()

        print("all demo returns calculated")


def daily_returns7():
    from tvDatafeed import TvDatafeed, Interval

    today = timezone.now().date()

    lagos_timezone = pytz.timezone("Africa/Lagos")
    current_time_lagos = timezone.now().astimezone(lagos_timezone)
    # print(current_time_lagos)

    # if current_time_lagos.time() >= datetime.strptime('8:02 AM', '%I:%M %p').time() and current_time_lagos.time() <= datetime.strptime('11:31 PM', '%I:%M %p').time() and current_time_lagos.weekday() < 5:
    if (
        current_time_lagos.time() >= datetime.strptime("10:02 AM", "%I:%M %p").time()
        and current_time_lagos.time() <= datetime.strptime("2:30 PM", "%I:%M %p").time()
        and current_time_lagos.weekday() < 5
    ):

        portfolios = DemoPortfolio.objects.all()
        for portfolio in portfolios:
            positions_today = DemoPosition.objects.filter(
                portfolio=portfolio, status="close", updated__date=today
            )

            if positions_today.exists():
                print(f"{portfolio.user} closed position today")
                positions = DemoPosition.objects.filter(
                    portfolio=portfolio, status="close"
                )

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
                    "Amount_Invested": [
                        float(position.amount_invested) for position in positions
                    ],
                    "Profit_Loss": [
                        float(position.profit_loss) for position in positions
                    ],
                }
                df = pd.DataFrame(data)

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
                df["Daily_PortfolioReturns"] = (
                    df["Sum_Profit_Loss"] / df["Balance"] * 100
                )
                # print(df)

                df_final = df.groupby("Closedate").tail(1).reset_index(drop=True)
                # print(df_final)

                # Save the last row to the database
                last_row = df_final.iloc[-1]
                d_returns = DemoDailyReturns2.objects.filter(
                    # user=portfolio.user,
                    portfolio=portfolio,
                    created__date=timezone.now().date(),
                    first_entry=False,
                ).order_by("-created")

                if d_returns.exists():
                    if len(d_returns) > 1:
                        d_returns = d_returns.order_by("-created")[1]
                    d_returns = d_returns.first()
                    d_returns.portfolio_returns = round(
                        last_row["Daily_PortfolioReturns"], 2
                    )
                    d_returns.created = timezone.now()
                    d_returns.save()
                else:
                    DemoDailyReturns2.objects.create(
                        # user=portfolio.user,
                        portfolio=portfolio,
                        portfolio_returns=round(last_row["Daily_PortfolioReturns"], 2),
                        created=timezone.now(),
                        first_entry=False,
                    )

                cum_table = df_final[["closedatetime", "Sum_Profit_Loss", "Balance"]]
                cum_table = cum_table.reset_index(drop=True)
                cum_table["running_pl"] = cum_table["Sum_Profit_Loss"].cumsum()
                cum_table["cum_returns"] = (
                    cum_table.running_pl / cum_table.Balance
                ) * 100

                print(cum_table)
                last_row_cum = cum_table.iloc[-1]

                c_returns = DemoCumulativeReturns.objects.filter(
                    portfolio=portfolio,
                    created__date=timezone.now().date(),
                    first_entry=False,
                )

                if c_returns.exists():
                    c_returns = c_returns.first()
                    c_returns.portfolio_returns = round(last_row_cum["cum_returns"], 2)
                    c_returns.created = timezone.now()
                    c_returns.save()
                else:
                    DemoCumulativeReturns.objects.create(
                        # user=portfolio.user,
                        portfolio=portfolio,
                        portfolio_returns=round(last_row_cum["cum_returns"], 2),
                        created=timezone.now(),
                        first_entry=False,
                    )

                tv = TvDatafeed()

                # days_passed = days_since_date('2024-05-1')
                comparison_date = "2024-07-15"
                portfolio_creation_date = portfolio.created.date().strftime("%Y-%m-%d")
                if portfolio_creation_date < comparison_date:
                    days_passed = days_since_date(comparison_date)
                else:
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
                ASI_daily_selected["Date"] = ASI_daily_selected["datetime"].dt.strftime(
                    "%Y-%m-%d"
                )

                # print(ASI_daily_selected)
                # # Save the last row to the database
                last_row_market = ASI_daily_selected.iloc[-1]
                # print(last_row_market)

                market_returns = last_row_market["ASI_daily_retuns"]
                if np.isnan(market_returns):
                    market_returns = 0

                d_returns.market_returns = round(market_returns, 2)
                d_returns.save()

                cum_mark_table = ASI_daily_selected[["Date", "ASI_daily_retuns"]]
                cum_mark_table["cum_ASI_daily_retuns"] = (
                    1 + cum_mark_table.ASI_daily_retuns / 100
                ).cumprod() - 1
                cum_mark_table["cum_ASI_daily_retuns"] = (
                    cum_mark_table.cum_ASI_daily_retuns * 100
                )

                # print(cum_mark_table)
                last_row_cum_market = cum_mark_table.iloc[-1]
                # print(last_row_cum_market)
                cum_market_returns = last_row_cum_market["cum_ASI_daily_retuns"]
                if np.isnan(cum_market_returns):
                    cum_market_returns = 0

                c_returns.market_returns = round(cum_market_returns, 2)
                c_returns.save()

        print("all demo returns calculated")
