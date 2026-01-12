import decimal
import os
import time as pytime
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, time

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
    collection = db_merged["merged_live_price"]
    last_item = collection.find_one(sort=[("_id", -1)])
    return last_item


def calculate_profit_loss(position, price):
    quantity = position["quantity"]
    amount_invested = position["amount_invested"]
    status = position["status"]
    action = position["action"]

    current_value = round(quantity * price, 2)
    profit_loss = 0

    if status == "open":
        if action == "buy":
            profit_loss = decimal.Decimal(current_value) - amount_invested
        elif action == "sell":
            profit_loss = amount_invested - decimal.Decimal(current_value)
    elif status == "close":
        profit_loss = position["profit_loss"]
        current_value = quantity * position["close_price"]

    return profit_loss, current_value, price


def get_equity_balance(portfolio, positions, last_item):
    """
    Calculate equity balance for a portfolio based on its positions.
    Args:
        portfolio (dict): Portfolio data with balance and account_id.
        positions (dict): Dictionary of positions keyed by portfolio_id.

    Returns:
        dict: Data containing balance, equity, timestamp, and account_id.
    """
    # Get balance from portfolio
    print(portfolio)
    # print(positions)
    balance = portfolio["balance"]
    account_id = portfolio["account_id"]

    # Get positions for this portfolio
    portfolio_id = portfolio["id"]
    portfolio_positions = positions.get(portfolio_id, [])  # Retrieve positions directly

    # Initialize profit/loss and open balance
    total_profit_loss = 0
    open_balance = 0

    # Calculate profit/loss and current value for each position
    for position in portfolio_positions:
        stock_symbol = position["stock_symbol"]
        quantity = position["quantity"]
        open_price = position["open_price"]
        action = position["action"]
        status = position["status"]

        # Get current price of stock
        current_price_data = last_item[stock_symbol]
        current_price = current_price_data.get("current_price", 0)

        if status == "open":
            current_value = quantity * current_price
            if action == "buy":
                profit_loss = current_value - float((quantity * open_price))
            elif action == "sell":
                profit_loss = float((quantity * open_price)) - current_value
            else:
                profit_loss = 0

            total_profit_loss += profit_loss
            open_balance += quantity * open_price

    # Calculate equity
    equity = max(float(balance) + total_profit_loss, 0)

    # Prepare response data
    data = {
        "balance": round(float(balance + open_balance), 2),
        "equity": round(equity + float(open_balance), 2),
        "timestamp": datetime.now(WAT_TIMEZONE).strftime("%Y-%m-%dT%H:%M"),
        "account_id": account_id,
    }

    return data


def fetch_portfolio_data():
    """Fetch distinct portfolios and their corresponding positions with stock symbols from PostgreSQL."""
    conn = get_postgres_connection()
    cursor = conn.cursor(cursor_factory=DictCursor)

    try:
        cursor.execute(
            """
            SELECT dp.id AS portfolio_id, dp.balance, dp.account_id, 
                   dpos.id AS position_id, dpos.stock_id, dpos.quantity, 
                   dpos.open_price, dpos.close_price, dpos.status, 
                   dpos.action, stock.symbol AS stock_symbol
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
                    "account_id": row["account_id"],
                }

            # Group positions by portfolio
            if row["position_id"]:
                if portfolio_id not in positions:
                    positions[portfolio_id] = []
                positions[portfolio_id].append(
                    {
                        "position_id": row["position_id"],
                        "stock_id": row["stock_id"],
                        "quantity": row["quantity"],
                        "open_price": row["open_price"],
                        "close_price": row["close_price"],
                        "status": row["status"],
                        "action": row["action"],
                        "stock_symbol": row["stock_symbol"],
                    }
                )

        return portfolios, positions

    finally:
        cursor.close()
        conn.close()


def process_balance_equity_data():
    """Process and store balance and equity data during trading hours."""
    portfolios, positions = fetch_portfolio_data()
    print("all fetched")
    # print(portfolios)
    # print(positions)

    current_datetime = datetime.now(WAT_TIMEZONE)
    current_time = current_datetime.time()
    current_day = current_datetime.weekday()
    last_item = get_price()

    # Only process during trading hours (Monday-Friday, 10:00-14:30)
    if 0 <= current_day <= 4 and time(8, 0) <= current_time <= time(14, 42):
        for portfolio in portfolios.values():
            account_data = get_equity_balance(portfolio, positions, last_item)

            # Format data for MongoDB
            mongo_data = {
                "balance": float(account_data["balance"]),
                "equity": float(account_data["equity"]),
                "timestamp": account_data["timestamp"],
                "account_id": account_data["account_id"],
            }

            print(mongo_data)

            # Insert into MongoDB
            collection = db_prop[portfolio["account_id"]]
            collection.insert_one(mongo_data)


if __name__ == "__main__":
    while True:
        try:
            process_balance_equity_data()

            # Sleep for 2 minutes
        except Exception as e:
            print(f"Error occurred: {e}")
        # process_balance_equity_data()
        print("sleeping...")
        pytime.sleep(120)
        pytime.sleep(120)
