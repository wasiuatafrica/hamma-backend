import requests
from dotenv import load_dotenv
import os
from tvDatafeed import TvDatafeed, Interval
from pymongo import MongoClient
from datetime import datetime, timedelta, time
import pytz
import pandas as pd
import numpy as np
import random
import time as module_time
import json

load_dotenv()

TOKEN=os.environ.get('TOKEN')
MONGO_URL=os.environ.get('MONGO_URL')

lagos_tz = pytz.timezone('Africa/Lagos')

# Get current time in Lagos timezone



def connect_to_mongodb(dbase):
    client = MongoClient(MONGO_URL,maxPoolSize=20,tls=True, tlsAllowInvalidCertificates=True)
    db = client[dbase]
    return db


def write_to_mongodb(dbase,data):
    db = connect_to_mongodb(dbase)
    collection = db["live_price_combined"]
    collection.insert_one(data)
    

def get_live_data()    :
    url = f"https://marketdataapiv3.ngxgroup.com/v3/api/price/pricesRT.json?_t={TOKEN}"
    payload={}
    headers = {}
    response = requests.request("GET", url, headers=headers, data=payload)
    symbol_list = response.json()

    lagos_now = datetime.now(lagos_tz)
    
    equity = [data for data in symbol_list if data['Asset']=='EQUITY' and datetime.fromisoformat(data["TradeDate"]).date() ==  lagos_now.date() ]
    
    

    combined = {}

    for data in equity:
        
        symbol=data['Symbol'].split(' ')[0]
        
        data1= {'datetime': lagos_now.strftime("%Y-%m-%d %H:%M:%S"),  'open': data['Open'], 'high': data['High'], 'low': data['Low'], 'close': data['Close'], 'volume': data['Volume'], 'symbol': symbol}
        
        combined[symbol] = data1
          
    write_to_mongodb("livelake3", combined)
      
def is_market_open():
    lagos_timezone = pytz.timezone('Africa/Lagos')
    current_time_lagos = datetime.now(lagos_timezone).time()

    if datetime.today().weekday() < 5:
        market_open_time = time(9, 55)
        # market_close_time = time(18, 30)
        market_close_time = time(14, 37)

        if market_open_time <= current_time_lagos <= market_close_time:
            return True

    return False

while True:
    today = datetime.today().weekday()
    if is_market_open() and today < 5:
        get_live_data()
        lagos_now = datetime.now(lagos_tz)
        print("Live Price Updated" , lagos_now.strftime("%Y-%m-%d %H:%M:%S"))
    else:
        print("Market closed - Live")
    module_time.sleep(60)
        