import concurrent.futures
import multiprocessing
import random
import threading
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pandas_market_calendars as mcal
from pymongo import MongoClient
import os
from pathlib import Path
import environ

environ.Env.read_env(Path(__file__).resolve().parent / ".env")


def connect_to_mongodb():
    client = MongoClient(
        os.environ["MONGO_STRING"],
        tls=True,
        tlsAllowInvalidCertificates=True,
    )
    db = client["anyon_orderbook"]
    # db2 = client["anyon2"]
    return db


def generate_candlestick_data(symbol):
    start_date = datetime(2021, 11, 12)
    candlestick_data = []

    # Use a different random seed for each symbol
    random.seed(symbol)

    # Use a geometric Brownian motion model to simulate the stock prices
    # Source:
    S0 = round(random.uniform(50, 200), 2)  # Initial price
    mu = 0.05  # Drift
    sigma = 0.2  # Volatility
    T = 2  # Time horizon in years
    N = 365 * T  # Number of time steps
    dt = T / N  # Time interval
    t = np.linspace(0, T, N)  # Time vector
    W = np.random.standard_normal(size=N)  # Brownian increments
    W = np.cumsum(W) * np.sqrt(dt)  # Cumulative Brownian noise
    X = (mu - 0.5 * sigma**2) * t + sigma * W  # Log returns
    S = S0 * np.exp(X)  # Stock prices

    # Generate the candlestick data for each trading day
    for i in range(N):
        trade_date = start_date.strftime("%Y-%m-%d %H:%M:%S")
        trade_open = S[i]
        trade_high = trade_open + random.uniform(0, 10)
        trade_low = trade_open - random.uniform(0, 10)
        trade_close = round(random.uniform(trade_low, trade_high), 2)
        trade_volume = random.randint(1000, 5000)

        candlestick_data.append(
            {
                "symbol": symbol,
                "datetime": trade_date,
                "open": trade_open,
                "high": trade_high,
                "low": trade_low,
                "close": trade_close,
                "volume": trade_volume,
            }
        )

        start_date += timedelta(days=1)
        print(f"data generated for {symbol} on {trade_date}")

    return candlestick_data


def generate_order_book_data(symbol):
    start_date = datetime(2021, 11, 12)
    order_book_data = []

    # Use a different random seed for each symbol
    random.seed(symbol + "order")

    # Use the same geometric Brownian motion model as above, but with different parameters
    # Source:
    S0 = round(random.uniform(50, 200), 2)  # Initial price
    mu = 0.03  # Drift
    sigma = 0.15  # Volatility
    T = 2  # Time horizon in years
    N = 365 * T  # Number of time steps
    dt = T / N  # Time interval
    t = np.linspace(0, T, N)  # Time vector
    W = np.random.standard_normal(size=N)  # Brownian increments
    W = np.cumsum(W) * np.sqrt(dt)  # Cumulative Brownian noise
    X = (mu - 0.5 * sigma**2) * t + sigma * W  # Log returns
    S = S0 * np.exp(X)  # Stock prices

    # Generate the order book data for each trading day
    for i in range(N):
        order_date = start_date.strftime("%Y-%m-%d %H:%M:%S")
        bid_price = S[i]
        ask_price = bid_price + random.uniform(0, 5)
        bid_quantity = random.randint(500, 2000)
        ask_quantity = random.randint(500, 2000)

        order_book_data.append(
            {
                "symbol": symbol,
                "datetime": order_date,
                "bid_price": bid_price,
                "ask_price": ask_price,
                "bid_quantity": bid_quantity,
                "ask_quantity": ask_quantity,
            }
        )

        start_date += timedelta(days=1)
        print(f"order book generated for {symbol} on {order_date}")

    return order_book_data


def generate_and_save(symbol):
    # Use a market calendar to get the valid trading days
    # Source:
    nyse = mcal.get_calendar("NYSE")
    schedule = nyse.schedule(start_date="2021-11-12", end_date="2023-11-12")
    valid_days = mcal.date_range(schedule, frequency="1D")

    # candlestick_data = generate_candlestick_data(symbol)
    order_book_data = generate_order_book_data(symbol)

    db = connect_to_mongodb()
    # candlestick_collection = db[symbol]

    # # Filter out the data that are not on valid trading days
    # candlestick_data = [data for data in candlestick_data if data['datetime'][:10] in valid_days]
    # candlestick_collection.insert_many(candlestick_data)

    order_book_collection = db[symbol]
    order_book_data = [
        data for data in order_book_data if data["datetime"][:10] in valid_days
    ]
    order_book_collection.insert_many(order_book_data)
    print(f"stock data and order book generated for {symbol}")


def read_excel_second_column(file_path):
    try:
        df = pd.read_excel(file_path)
        second_column_values = df.iloc[:, 1].tolist()
        return second_column_values
    except Exception as e:
        print(f"Error reading Excel file: {e}")
        return None


def main():
    stocks = read_excel_second_column("./stocks.xlsx")
    print("stocks fetched")

    with concurrent.futures.ThreadPoolExecutor() as executor:
        executor.map(generate_and_save, stocks)


if __name__ == "__main__":
    main()
if __name__ == "__main__":
    main()
