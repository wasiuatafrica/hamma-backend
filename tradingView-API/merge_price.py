import requests
from dotenv import load_dotenv
import os
from pymongo import MongoClient
import pandas as pd
from datetime import datetime
import pytz
from datetime import datetime, timedelta, time
import time as module_time
import math


# Load environment variables
load_dotenv()

MONGO_URL = os.environ.get('MONGO_URL')

# Function to connect to MongoDB
def connect_to_mongodb(db_name):
    client = MongoClient(MONGO_URL, tls=True, tlsAllowInvalidCertificates=True)
    db = client[db_name]
    return db

# Function to get last item from "stock_prices" collection
def get_price():
    db = connect_to_mongodb("stock_prices")
    collection = db["price_combined"]
    last_item = collection.find_one(sort=[('_id', -1)])
    return last_item

# Function to get all items from "live_price_combined"
def get_live():
    db = connect_to_mongodb("livelake3")
    collection = db["live_price_combined"]
    all_items = list(collection.find().sort('_id'))
    return all_items

# Function to get a DataFrame with data for a specific symbol
def get_symbol_data(all_items, symbol):
    symbol_data = []
    for item in all_items:
        if symbol in item:
            symbol_dict = item[symbol]
            symbol_data.append(symbol_dict)
    return pd.DataFrame(symbol_data)



def safe_float(value):
    """
    Returns a safe float value. Converts `inf` and `NaN` to None or a default value.
    """
    if isinstance(value, float):
        if math.isinf(value) or math.isnan(value):
            return None  # or return 0, or any other safe value
    return value

def get_combined():
    volatile_data = get_price()
    all_live_data = get_live()
    live_data = all_live_data[-1]

    # Combined data storage
    combined = {}

    # Process each symbol in volatile_data except '_id' and 'ASI'
    for symbol, data in volatile_data.items():
        if symbol != '_id' and symbol != 'ASI' and data:
            data2 = live_data.get(symbol, None)  # Get live data for the symbol
            if data2 is None:
                continue  # Skip if there's no live data for this symbol

            # Get the symbol-specific data as a DataFrame
            df = get_symbol_data(all_live_data, symbol)
            # print(df)
            # Convert 'datetime' to datetime objects and set as index
            df['datetime'] = pd.to_datetime(df['datetime'])
            df = df.set_index('datetime').sort_index()

            # Ensure 'close' column doesn't contain None or NaN
            df['close'] = df['close'].ffill().fillna(0)  # Forward-fill and then fill any remaining NaNs with 0

            # Filter out rows where the close price remains unchanged
            df = df[df['close'].diff() != 0]

            # Calculate 'change' and 'pct_change'
            df['change'] = df['close'].diff().fillna(0)
            df['pct_change'] = (df['close'].pct_change() * 100).fillna(0)

            df['change'] = df['change'].round(2)
            df['pct_change'] = df['pct_change'].round(2)

            # Replace any infinite values in 'pct_change' with a safe default
            df['pct_change'] = df['pct_change'].apply(safe_float)
            
            # Find the last non-zero 'change' and 'pct_change'
            last_non_zero_change = safe_float(df['change'].iloc[-1] if not df.empty else 0)
            last_non_zero_pct_change = safe_float(df['pct_change'].iloc[-1] if not df.empty else 0)

            # Prepare the new data with the last change and percentage change
            new_data = {
                'datetime': data2['datetime'],
                'symbol': symbol,
                'open': data2['open'],
                'high': data2['high'],
                'low': data2['low'],
                'close': data2['close'],
                'volume': data2['volume'],
                'change': last_non_zero_change,
                'percentage_change': last_non_zero_pct_change,
                'current_price': data2['close'],
                'volatility': data.get('volatility', None),
                'momentum': data.get('momentum', None),
            }

            # Store the new data in combined
            combined[symbol] = new_data
    combined['BAPLC'] = {
        'datetime': live_data['BAPLC']['datetime'],
        'symbol': 'BAPLC',
        'open': live_data['BAPLC']['open'],
        'high': live_data['BAPLC']['high'],
        'low': live_data['BAPLC']['low'],
        'close': live_data['BAPLC']['close'],
        'volume': live_data['BAPLC']['volume'],
        'change': 0,
        'percentage_change': 0,
        'current_price': live_data['BAPLC']['close'],
        'volatility': 0,
        'momentum': 0,
    }
    return combined


def write_to_mongodb(dbase,data):
    db = connect_to_mongodb(dbase)
    collection = db["merged_live_price"]
    collection.insert_one(data)

def is_market_open():
    lagos_timezone = pytz.timezone('Africa/Lagos')
    current_time_lagos = datetime.now(lagos_timezone).time()

    if datetime.today().weekday() < 5:
        market_open_time = time(10, 00)
        market_close_time = time(14, 37)
        # market_open_time = time(7, 55)
        # market_close_time = time(18, 31)

        if market_open_time <= current_time_lagos <= market_close_time:
            return True

    return False

while True:
    today = datetime.today().weekday()
    if is_market_open() and today < 5:
        combined = get_combined()   
        # print(combined)
        write_to_mongodb("livelake3", combined)
        print("Live Price merged")
    else:
        print("Market closed")
    module_time.sleep(59)