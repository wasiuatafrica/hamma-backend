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

def get_live():
    db = connect_to_mongodb("livelake3")
    collection = db["live_price_combined"]
    all_items = list(collection.find().sort('_id'))
    return all_items

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
    print('volatile gotten')
    all_live_data = get_live()
    print('all live gotten')
    live_data = all_live_data[-1]

    # Combined data storage
    combined = {}

    # Process each symbol in volatile_data except '_id' and 'ASI'
    for symbol, data in live_data.items():
        if symbol != '_id':
            data2 = volatile_data.get(symbol, None)  
            df = get_symbol_data(all_live_data, symbol)
            # print(df)
            df['datetime'] = pd.to_datetime(df['datetime'])
            df = df.set_index('datetime').sort_index()

            # Ensure 'close' column doesn't contain None or NaN
            df['close'] = df['close'].ffill().fillna(0)  

            # Filter out rows where the close price remains unchanged
            df = df[df['close'].diff() != 0]

            # Calculate 'change' and 'pct_change'
            df['change'] = df['close'].diff().fillna(0)
            df['pct_change'] = (df['close'].pct_change() * 100).fillna(0)

            df['change'] = df['change'].round(2)
            df['pct_change'] = df['pct_change'].round(2)

            # Replace any infinite values in 'pct_change' with a safe default
            df['pct_change'] = df['pct_change'].apply(safe_float)
            
            last_non_zero_change = 0
            last_non_zero_pct_change = 0

            for idx in df.index[::-1]:  # Reverse iteration
                change = df.loc[idx, 'change']  # Get the 'change' value at this index
                if change != 0:  
                    last_non_zero_change = safe_float(change)  
                    last_non_zero_pct_change = safe_float(df.loc[idx, 'pct_change']) 
                    break  

            # Prepare the new data with the last change and percentage change
            if data2:
                new_data = {
                    'datetime': data['datetime'],
                    'symbol': symbol,
                    'open': data['open'],
                    'high': data['high'],
                    'low': data['low'],
                    'close': data['close'],
                    'volume': data['volume'],
                    'change': last_non_zero_change,
                    'percentage_change': last_non_zero_pct_change,
                    'current_price': data['close'],
                    'volatility': data2.get('volatility', None),
                    'momentum': data2.get('momentum', None),
                    'volatility_1week': data2.get('volatility_1week', None),
                    'momentum_1week': data2.get('momentum_1week', None),
                    'volatility_1year': data2.get('volatility_1year', None),
                    'momentum_1year': data2.get('momentum_1year', None),
                    'volatility_ytd': data2.get('volatility_ytd', None),
                    'momentum_ytd': data2.get('momentum_ytd', None),
                    'volatility_24hr': data2.get('volatility_24hr', None),
                    'momentum_24hr': data2.get('momentum_24hr', None),
                }
            else:
                new_data = {
                    'datetime': data['datetime'],
                    'symbol': symbol,
                    'open': data['open'],
                    'high': data['high'],
                    'low': data['low'],
                    'close': data['close'],
                    'volume': data['volume'],
                    'change': last_non_zero_change,
                    'percentage_change': last_non_zero_pct_change,
                    'current_price': data['close'],
                    'volatility': 0,
                    'momentum': 0,
                    'volatility_1week': 0,
                    'momentum_1week': 0,
                    'volatility_1year': 0,
                    'momentum_1year': 0,
                    'volatility_ytd': 0,
                    'momentum_ytd': 0,
                    'volatility_24hr': 0,
                    'momentum_24hr': 0,
                }
            print(new_data)
            combined[symbol] = new_data
    return combined


def write_to_mongodb(dbase,data):
    db = connect_to_mongodb(dbase)
    collection = db["merged_live_price"]
    collection.insert_one(data)

def is_market_open():
    lagos_timezone = pytz.timezone('Africa/Lagos')
    current_time_lagos = datetime.now(lagos_timezone).time()
    # print(current_time_lagos)

    if datetime.today().weekday() < 5:
        market_open_time = time(10, 2)
        market_close_time = time(14, 32)
        # market_open_time = time(7, 30)
        # market_close_time = time(22, 31)

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
        print("Market closed - Merge")
    module_time.sleep(59)