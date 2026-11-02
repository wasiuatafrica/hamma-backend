import decimal
import os
import time as pytime
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, time
from decimal import Decimal
from typing import Dict, List, Union

import psycopg2
from psycopg2.extras import DictCursor
from pymongo import MongoClient
from pytz import timezone

# Configuration
POSTGRES_SETTINGS = {
    "dbname": "d750fkaab218jq",
    "user": "uf30d8l7tq8smq",
    "password": "pa74b92662bed576278ed36056323f25f705be75d9118b3170c9830f7a28d0623",
    "host": "c3opaibi71ph4s.cluster-czrs8kj4isg7.us-east-1.rds.amazonaws.com",
    "port": 5432,
}

WAT_TIMEZONE = timezone("Africa/Lagos")

# MongoDB Client
mongo_client = MongoClient(
    "mongodb+srv://ft9jatraders_db_user:HnyOs6KBOwGKjJmy@reducebill.yxn3gnr.mongodb.net/",
    maxPoolSize=20,
    tls=True,
    tlsAllowInvalidCertificates=True,
)
db_prop = mongo_client["prop_data_prod"]
db_merged = mongo_client["livelake3"]


# Connect to PostgreSQL
def get_postgres_connection():
    return psycopg2.connect(**POSTGRES_SETTINGS)


def get_price():
    # collection = db_merged["merged_live_price"]
    collection = db_merged["merged_live_price_trdv"]
    last_item = collection.find_one(sort=[("_id", -1)])
    return last_item


# Simple class to hold position metrics
class PositionMetrics:
    def __init__(
        self,
        profit_loss=Decimal("0"),
        current_value=Decimal("0"),
        commission=Decimal("0"),
        swap_fee=Decimal("0"),
        percent_change=0.0,
    ):
        self.profit_loss = profit_loss
        self.current_value = current_value
        self.commission = commission
        self.swap_fee = swap_fee
        self.percent_change = percent_change


def calculate_position_metrics(position, last_item):
    """Calculate core metrics for a single position"""
    # Convert values to Decimal for precision
    quantity = Decimal(str(position["quantity"]))
    amount_invested = Decimal(str(position["quantity"] * position["open_price"]))
    status = position["status"]
    action = position["action"]

    # Get current price of stock
    stock_symbol = position["stock_symbol"]
    current_price_data = last_item.get(stock_symbol, {})
    current_price = Decimal(
        str(current_price_data.get("current_price", position["open_price"]))
    )

    if status == "open":
        current_value = Decimal(str(round(quantity * current_price, 2)))

        if action == "buy":
            profit_loss = current_value - amount_invested
        else:  # sell
            profit_loss = amount_invested - current_value

        commission = Decimal("0")
        swap_fee = Decimal(str(position.get("swap_fee", 0)))

    elif status == "close":
        close_price = Decimal(str(position["close_price"] or 0))
        current_value = quantity * close_price

        profit_loss = Decimal(str(position["profit_loss"]))
        commission = round(
            (Decimal("0.00435") * Decimal(str(position["amount_invested"])))
            + Decimal("200"),
            2,
        )
        swap_fee = Decimal(str(position.get("swap_fee", 0)))
    else:
        return PositionMetrics()

    # Calculate percent change
    percent_change = (
        round(float(profit_loss) / float(amount_invested) * 100, 2)
        if amount_invested != 0
        else 0.0
    )

    return PositionMetrics(
        profit_loss=profit_loss,
        current_value=current_value,
        commission=commission,
        swap_fee=swap_fee,
        percent_change=percent_change,
    )


def fetch_portfolio_data():
    """Fetch distinct portfolios and their corresponding positions with stock symbols from PostgreSQL."""
    conn = get_postgres_connection()
    cursor = conn.cursor(cursor_factory=DictCursor)

    try:
        cursor.execute(
            """
            SELECT dp.id AS portfolio_id, dp.balance, dp.initial_balance, dp.account_id, 
                   dpos.id AS position_id, dpos.stock_id, dpos.quantity, 
                   dpos.open_price, dpos.close_price, dpos.status, 
                   dpos.action, dpos.amount_invested, dpos.created, dpos.closed_at, dpos.profit_loss,dpos.swap_fee,
                   stock.symbol AS stock_symbol, stock.logo_url, dpos.order_type
            FROM execution_demoportfolio dp
            LEFT JOIN execution_demoposition dpos ON dp.id = dpos.portfolio_id
            LEFT JOIN portfolio_stock stock ON dpos.stock_id = stock.id
            WHERE dp.is_prop = TRUE 
            AND dp.is_active = TRUE
            AND dp.inactive_by_inactivity = FALSE
            AND dp.activated = TRUE
            AND dp.blown = FALSE
            AND dp.has_hamma_id IS NULL;
            """
        )
        results = cursor.fetchall()

        # Organize data
        portfolios = {}
        positions = {}
        for row in results:
            portfolio_id = row["portfolio_id"]

            # Ensure portfolio is added only once
            if portfolio_id not in portfolios:
                portfolios[portfolio_id] = {
                    "id": portfolio_id,
                    "balance": row["balance"],
                    "initial_balance": row["initial_balance"],
                    "account_id": row["account_id"],
                }

            # Group positions by portfolio
            if row["position_id"]:
                if portfolio_id not in positions:
                    positions[portfolio_id] = []
                positions[portfolio_id].append(dict(row))

        return portfolios, positions

    finally:
        cursor.close()
        conn.close()


def calculate_portfolio_metrics(portfolio, position_list, last_item):
    """Calculate complete portfolio metrics using the enhanced calculator logic"""
    total_floating_pl = Decimal("0")
    total_closed_pl = Decimal("0")
    open_balance = Decimal("0")
    total_swap_fees_open_positions = Decimal("0")

    # Process each position
    for position in position_list:
        metrics = calculate_position_metrics(position, last_item)

        if position["status"] == "open":
            total_floating_pl += metrics.profit_loss
            open_balance += Decimal(str(position["amount_invested"]))
            total_swap_fees_open_positions += metrics.swap_fee
        else:
            # For closed positions, use net profit (profit_loss - commission - swap_fee)
            net_profit = metrics.profit_loss - metrics.commission - metrics.swap_fee
            total_closed_pl += net_profit
    # print(total_closed_pl)

    # Calculate final balance and equity
    initial_balance = Decimal(str(portfolio["initial_balance"]))
    current_balance = initial_balance + total_closed_pl - total_swap_fees_open_positions
    equity = current_balance + total_floating_pl

    return {
        "balance": float(current_balance),
        "floating_pl": float(total_floating_pl),
        "closed_pl": float(total_closed_pl),
        "equity": float(equity),
        "open_balance": float(open_balance),
    }


def process_balance_equity_data():
    """Process and store balance and equity data during trading hours using enhanced calculator logic."""
    portfolios, positions = fetch_portfolio_data()

    current_datetime = datetime.now(WAT_TIMEZONE)
    current_time = current_datetime.time()
    current_day = current_datetime.weekday()
    last_item = get_price()

    # Only during NGX continuous trading, 09:30-15:50, plus 12 minutes (standalone
    # script: keep in step with portfolio/market_hours.py)
    if 0 <= current_day <= 4 and time(9, 30) <= current_time <= time(16, 2):
        for portfolio_id, portfolio in portfolios.items():
            # print(portfolio["account_id"])
            # Get positions for this portfolio
            portfolio_positions = positions.get(portfolio_id, [])

            # Calculate portfolio metrics using enhanced calculator logic
            metrics = calculate_portfolio_metrics(
                portfolio, portfolio_positions, last_item
            )

            # Format data for MongoDB
            mongo_data = {
                "balance": metrics["balance"],
                "equity": metrics["equity"],
                "timestamp": current_datetime.strftime("%Y-%m-%dT%H:%M"),
                "account_id": portfolio["account_id"],
            }


            # Insert into MongoDB
            collection = db_prop[portfolio["account_id"]]
            collection.insert_one(mongo_data)


if __name__ == "__main__":
    while True:
        try:
            process_balance_equity_data()
        except Exception as e:
            pass

        pytime.sleep(120)
        pytime.sleep(120)
