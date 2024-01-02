from django.core.mail import send_mail
from pymongo import MongoClient
import json
from bson import json_util
import websockets
import asyncio

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



async def connect_to_websocket(stock_symbol):
    # uri = f"ws://localhost:8765/{stock_symbol}"
    uri = f"ws://ec2-16-16-77-63.eu-north-1.compute.amazonaws.com:8765/{stock_symbol}"

    async with websockets.connect(uri) as websocket:
        try:
            # Sending authentication token
            auth_token = "Ab$455"
            await websocket.send(auth_token)

            
            data = await websocket.recv()
            stock_data = json.loads(data)
            print(stock_data)
            return stock_data
        except websockets.exceptions.ConnectionClosed as e:
            if e.code != 1000:
                print(f"Connection closed unexpectedly: {e}")
                
def get_price(stock):
    return asyncio.run(connect_to_websocket(stock))

def get_details(stock):
    data = get_price(stock.symbol)
    details = {
        'company':stock.company,
        'symbol':stock.symbol,
        'sector': stock.sector,
        'current_price':data['current_price'],
        "percent_change":data['percentage_change'],
        'change':round(data['current_price'] - data['open_price'],2)
    }
    
    return details
    
    
async def connect_to_websockets2(symbols):
    results = {}

    async def connect(symbol):
        uri = f"ws://ec2-16-16-77-63.eu-north-1.compute.amazonaws.com:8765/{symbol}"
        async with websockets.connect(uri) as websocket:
            # Sending authentication token for each symbol
            auth_token = "Ab$455"
            await websocket.send(auth_token)

            data = await websocket.recv()
            stock_data = json.loads(data)
            print(stock_data)
            results[symbol] = stock_data
            return symbol
    
    # Launch all the connect coroutines and wait for them to finish
    await asyncio.gather(*(connect(symbol) for symbol in symbols))
    return results

# async def connect_to_websockets3(symbols):
#     uri = "ws://ec2-16-16-77-63.eu-north-1.compute.amazonaws.com:8765"
#     results = {}
#     auth_token = "Ab$455"

#     # Connect to WebSocket server once
#     async with websockets.connect(uri) as websocket:
#         # Send authentication token
#         await websocket.send(auth_token)

#         # Subscribe to all symbols
#         subscribe_message = json.dumps({"action": "subscribe", "symbols": symbols})
#         await websocket.send(subscribe_message)

#         # Enter a loop to continuously receive data for subscribed symbols
#         try:
#             while True:
#                 data = await websocket.recv()
#                 stock_data = json.loads(data)
#                 symbol = stock_data['stock']
#                 results[symbol] = stock_data
#                 print(stock_data)

#                 # You could choose to break the loop after a certain condition,
#                 # but for the sake of this example, the loop will run indefinitely.
#         except websockets.exceptions.ConnectionClosed as e:
#             print(f"Connection closed: {e}")

#     return results



def get_stockdata(stocks):
    return asyncio.run(connect_to_websockets2(stocks))

# Your get_details now accepts a single data entry
def get_details2(stock, stock_data):
    data = stock_data[stock.symbol]
    return {
        'company': stock.company,
        'symbol': stock.symbol,
        'sector': stock.sector,
        'current_price': data['current_price'],
        "percent_change": data['percentage_change'],
        'change': round(data['current_price'] - data['open_price'],2)
    }

def get_details3(stocks):
    symbols =[stock.symbol for stock in stocks]
    stockdata= get_stockdata(symbols)
    return [get_details2(stock,stockdata) for stock in stocks]