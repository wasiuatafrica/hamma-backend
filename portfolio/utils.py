from django.core.mail import send_mail
from pymongo import MongoClient
import json
from bson import json_util
import websockets

def connect_to_mongodb(db_name):
    client = MongoClient("mongodb+srv://trademql5:trademql5@trademql5.fmlxv.mongodb.net/",tls=True,
                             tlsAllowInvalidCertificates=True)
    # db = client["anyon_orderbook"]
    db = client[db_name]
    return db


def get_symbol_data(symbol):
    db = connect_to_mongodb("anyon_orderbook")
    collection = db[symbol]
    
    # Sort the records in descending order based on some timestamp field (replace 'timestamp' with your actual field)
    records_cursor = collection.find().sort('timestamp', -1).limit(10)
    
    
    json_data= [       
                {
        "symbol": record['symbol'],
        "datetime":record['datetime'],
        "bid_price": record['bid_price'],
        "ask_price": record['ask_price'],
        "bid_quantity": record['bid_quantity'],
        "ask_quantity": record['ask_quantity']
        } 
                for record in records_cursor
            ]
    return json_data


def get_historical_data(symbol):
    db = connect_to_mongodb("anyon_history")
    collection = db[symbol]
    records = list(collection.find())
    serialized_records = json.loads(json_util.dumps(records))
    return serialized_records

# def get_mini_data():
#     db = connect_to_mongodb("anyon_history")
#     collection_names = db.list_collection_names()
#     # print(collection_names)
#     result_list = []
    
#     for collection_name in collection_names:
#         collection = db[collection_name]
#         last_27_items = list(collection.find().sort('datetime', -1).limit(27))
#         result_list.append({collection_name:json.loads(json_util.dumps(last_27_items))})
        
#     return result_list


def get_trend(closing_prices):
    # Function to determine the trend (up or down) based on closing prices
    if closing_prices[-1] > closing_prices[0]:
        return 'up'
    elif closing_prices[-1] < closing_prices[0]:
        return 'down'
    else:
        return 'neutral'

def get_mini_data():
    db = connect_to_mongodb("anyon_history")
    collection_names = db.list_collection_names()
    result_list = []
    
    for collection_name in collection_names:
        collection = db[collection_name]
        last_27_items = list(collection.find().sort('datetime', -1).limit(27))
        
        if len(last_27_items) >= 2:
            closing_prices = [item['close'] for item in last_27_items]
            trend = get_trend(closing_prices)
        else:
            trend = 'insufficient_data' 
            
        result_list.append({collection_name: trend})
        
    return result_list

def get_price(stock):
    uri = f"ws://ec2-16-16-77-63.eu-north-1.compute.amazonaws.com:8765/{stock}"
    with websockets.connect(uri) as websocket:
        try:
            # Sending authentication token
            auth_token = "Ab$455"
            websocket.send(auth_token)

            data = websocket.recv()
            stock_data = json.loads(data)
            print(stock_data)
            return stock_data
        except websockets.exceptions.ConnectionClosed as e:
            if e.code != 1000:
                print(f"Connection closed unexpectedly: {e}")