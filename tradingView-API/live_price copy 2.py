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
client = MongoClient(MONGO_URL,maxPoolSize=20,tls=True, tlsAllowInvalidCertificates=True)
db = client["livelake3"]
collection = db["live_price_combined"]
# Get current time in Lagos timezone





def write_to_mongodb(dbase,data):
    
    
    collection.insert_one(data)
    

# def get_live_data()    :
#     url = f"https://marketdataapiv3.ngxgroup.com/v3/api/price/pricesRT.json?_t={TOKEN}"
#     payload={}
#     headers = {}
#     response = requests.request("GET", url, headers=headers, data=payload)
#     symbol_list = response.json()

#     lagos_now = datetime.now(lagos_tz)
    
#     # equity = [data for data in symbol_list if data['Asset']=='EQUITY' and datetime.fromisoformat(data["TradeDate"]).date() ==  lagos_now.date() ]
#     equity = []
#     for data in symbol_list:
#         if data['Asset'] == 'EQUITY':
#             try:
#                 timestamp_str = data["Timestamp"]
                
#                 # Split the timestamp string into date and time parts
#                 date_part, time_part = timestamp_str.split('T')
                
#                 # Parse the date part
#                 data_date = datetime.strptime(date_part, '%Y-%m-%d').date()
                
#                 if data_date == lagos_now.date():
#                     equity.append(data)
#             except (ValueError, KeyError) as e:
#                 print(f"Error processing data: {data}, error: {e}")
        
        

#     combined = {}

#     for data in equity:
        
#         symbol=data['Symbol'].split(' ')[0]
        
#         current_time = datetime.fromisoformat(data["Timestamp"].split('+')[0]).time()
        
#         data1= {
#             'datetime': current_time.strftime("%Y-%m-%d %H:%M:%S"),  
#             'open': data['Open'], 
#             'high': data['High'] if data['High']  else round(data['Open']*1.01,2) , 
#             'low': data['Low'] if data['Low'] else round(data['Close']*0.99, 2),
#             'close': data['Close'], 
#             'volume': data['Volume'], 
#             'symbol': symbol,
#             'change': data['Change'],
#             'percent': data['PerChange']
#             }
        
#         combined[symbol] = data1
#     print(combined)     
#     # write_to_mongodb("livelake3", combined)

def get_live_data():
    url = f"https://marketdataapiv3.ngxgroup.com/v3/api/price/pricesRT.json?_t={TOKEN}"
    payload = {}
    headers = {}
    response = requests.request("GET", url, headers=headers, data=payload)
    symbol_list = response.json()

    lagos_tz = pytz.timezone('Africa/Lagos')
    lagos_now = datetime.now(lagos_tz)
    
    equity = []
    for data in symbol_list:
        # print(data)
        if data['Asset'] == 'EQUITY':
            try:
                timestamp_str = data["Timestamp"]
                
                # Split the timestamp string into date and time parts
                date_part, time_part = timestamp_str.split('T')
                time_part = time_part.split('+')[0].split('-')[0].split('.')[0]
                
                # Parse the date part
                data_date = datetime.strptime(date_part, '%Y-%m-%d').date()
                
                if data_date == lagos_now.date():
                    equity.append(data)
            except (ValueError, KeyError) as e:
                print(f"Error processing data: {data}, error: {e}")
        
    combined = {}

    print('equity',equity)
    if equity:
        for data in equity:
            symbol = data['Symbol'].split(' ')[0]
            
            try:
                # Manually handle the time part to avoid ValueError
                date_part, time_part = data["Timestamp"].split('T')
                time_part = time_part.split('+')[0].split('-')[0].split('.')[0]
                formatted_datetime = f"{date_part} {time_part}"
                current_time = datetime.strptime(formatted_datetime, '%Y-%m-%d %H:%M:%S')
                
                data1 = {
                    'datetime': current_time.strftime("%Y-%m-%d %H:%M:%S"),
                    'open': data['Open'], 
                    'high': data['High'] if data['High'] else round(data['Open'] * 1.01, 2), 
                    'low': data['Low'] if data['Low'] else round(data['Close'] * 0.99, 2),
                    'close': data['Close'], 
                    'volume': data['Volume'], 
                    'symbol': symbol,
                    'change': data['Change'],
                    'percent': data['PerChange']
                }
                
                combined[symbol] = data1
            except ValueError as e:
                print(f"Error processing datetime for data: {data}, error: {e}")
        
        print(combined)
        write_to_mongodb("livelake3", combined)
    else:
        print("No equity data found for the current date.")

      
def is_market_open():
    lagos_timezone = pytz.timezone('Africa/Lagos')
    current_time_lagos = datetime.now(lagos_timezone).time()

    if datetime.today().weekday() < 5:
        # market_open_time = time(10, 2)
        
        market_close_time = time(14, 40)
        market_open_time = time(7, 0)
        # market_close_time = time(22, 30)

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
        