from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, time
from decimal import Decimal
from pymongo import MongoClient
import os

import pytz
from django.utils import timezone

from execution.models import DemoPortfolio, DemoPosition

client = MongoClient(
    os.environ.get("MONGO_STRING"), tls=True, tlsAllowInvalidCertificates=True
)
if os.environ.get("server") == "local":
    db_prop = client["prop_data"]
else:
    db_prop = client["prop_data_prod"]

wat = pytz.timezone("Africa/Lagos")


def get_equity_balance(portfolio):
    balance = portfolio.balance
    positions = DemoPosition.objects.filter(portfolio=portfolio, status="open")

    def pl_cv(position):
        pl, cur_val, price = position.calculate_profit_loss()
        symbol = position.stock.symbol
        print(pl)
        data2 = {
            "stock": symbol,
            "current_value": round(cur_val, 2),
            "pl": pl,
            "open_date": position.created,
        }

        return pl, data2

    with ThreadPoolExecutor() as executor:
        futures = executor.map(pl_cv, positions)
        pl_cv_list = [result for result in futures if result]

    profit_loss_list = [x[0] for x in pl_cv_list]
    print(profit_loss_list)
    profit_loss = sum(profit_loss_list) if profit_loss_list else 0
    equity1 = round(balance + profit_loss, 2)
    equity = equity1 if equity1 >= 0 else 0

    open_balance = sum([position.amount_invested for position in positions])

    data = {
        "balance": round(balance + open_balance, 2),
        "equity": equity + open_balance,
        "timestamp": timezone.now().astimezone(wat).strftime("%Y-%m-%dT%H:%M"),
        "account_id": portfolio.account_id,
    }

    return data


def get_all_balance_equity_data():
    current_datetime = timezone.now().astimezone(wat)
    current_time = current_datetime.time()
    current_day = current_datetime.weekday()

    if 0 <= current_day <= 4:
        if time(10, 0) <= current_time <= time(14, 30):

            prop_accounts = DemoPortfolio.objects.filter(
                is_prop=True,
                is_active=True,
                inactive_by_inactivity=False,
                activated=True,
                blown=False,
            )
            for account in prop_accounts:
                account_data = get_equity_balance(account)
                mongo_data = {
                    "balance": (
                        float(account_data["balance"])
                        if isinstance(account_data["balance"], Decimal)
                        else account_data["balance"]
                    ),
                    "equity": (
                        float(account_data["equity"])
                        if isinstance(account_data["equity"], Decimal)
                        else account_data["equity"]
                    ),
                    "timestamp": (
                        account_data["timestamp"].strftime("%Y-%m-%dT%H:%M")
                        if isinstance(account_data["timestamp"], datetime)
                        else account_data["timestamp"]
                    ),
                    "account_id": account_data["account_id"],
                }

                collection = db_prop[account.account_id]
                collection.insert_one(mongo_data)


def get_account_data(account_id):
    collection = db_prop[account_id]
    data = list(collection.find({}, {"_id": 0}))
    return data if data else []
