from django.core.mail import send_mail
from pymongo import MongoClient
import json
from bson import json_util
from portfolio.serializers import AlertSerializer
import websockets
import asyncio
from openai import OpenAI
from django.contrib.auth import get_user_model
from .models import Alert, AlertAI, Conversation, Message
from concurrent.futures import ThreadPoolExecutor
import os
import math
from execution.symbol_pair import pairs

User= get_user_model()
client = MongoClient(os.environ.get("MONGO_STRING"),tls=True,
                             tlsAllowInvalidCertificates=True)

def connect_to_mongodb(db_name):
    
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
        "bid_price": round(record['bid_price'],2),
        "ask_price": round(record['ask_price'],2),
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



# async def connect_to_websocket(stock_symbol):
#     # uri = f"ws://localhost:8765/{stock_symbol}"
#     uri = f"ws://ec2-16-16-77-63.eu-north-1.compute.amazonaws.com:8765/{stock_symbol}"

#     async with websockets.connect(uri) as websocket:
#         try:
#             # Sending authentication token
#             auth_token = "Ab$455"
#             await websocket.send(auth_token)

            
#             data = await websocket.recv()
#             stock_data = json.loads(data)
#             print(stock_data)
#             return stock_data
#         except websockets.exceptions.ConnectionClosed as e:
#             if e.code != 1000:
#                 print(f"Connection closed unexpectedly: {e}")
                
# def get_price(stock):
#     return asyncio.run(connect_to_websocket(stock))

# def get_price(symbol):
#     db = connect_to_mongodb("stock_prices")
#     collection = db["price_combined"]
#     last_item = collection.find_one(sort=[('_id', -1)])
#     # print(last_item)
#     return last_item[symbol]

def get_price(symbol):
    from portfolio.utils import connect_to_mongodb
    db = connect_to_mongodb("livelake3")
    collection = db["merged_live_price"]
    last_item = collection.find_one(sort=[('_id', -1)])
    # print(symbol)
    return last_item[symbol]

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

# def get_stockdata2():
#     db = connect_to_mongodb("stock_prices")
#     collection = db["price_combined"]
#     last_item = collection.find_one(sort=[('_id', -1)])

#     return last_item

def get_stockdata2():
    db = connect_to_mongodb("livelake3")
    collection = db["merged_live_price"]
    last_item = collection.find_one(sort=[('_id', -1)])

    return last_item

# Your get_details now accepts a single data entry
# def get_details2(stock, stock_data):
#     # print(stock.symbol)
#     data = stock_data[stock.symbol]
#     print(data)
#     if data:
#         return {
#             'company': stock.company,
#             'symbol': stock.symbol,
#             'sector': stock.sector,
#             'current_price': data.get('current_price', 0),
#             "percent_change": data.get('percentage_change', 0),
#             # 'change': round(data['current_price'] - data['open_price'],2)
#             'change': data.get("change", 0)
#         }

def get_details2(stock, stock_data):
    data = stock_data.get(stock.symbol, {})
    # print(data)
    if data:
        return {
            'company': stock.company,
            'symbol': stock.symbol,
            'sector': stock.sector,
            "logo_url": stock.logo_url,
            # 'current_price': handle_special_values(data.get('current_price', 0)),
            # "percent_change": handle_special_values(data.get('percentage_change', 0)),
            # 'change': handle_special_values(data.get("change", 0)),
            # 'volume': handle_special_values(data.get("volume", 0)),
            # 'momentum': handle_special_values(data.get("momentum", 0)),
            # 'volatility': handle_special_values(data.get("volatility", 0)),
            'current_price': data.get('current_price'),
            "percent_change": data.get('percentage_change'),
            'change': data.get("change"),
            'volume': data.get("volume"),
            'momentum': data.get("momentum"),
            'momentum_change': data.get("momentum_change"),
            'volume_momentum':data.get('volume_momentum'),
            'volume_momentum_change':data.get('volume_momentum_change'),            
            'volatility': data.get("volatility"),
            
            'volatility_1week': data.get('volatility_1week'),
            'momentum_1week': data.get('momentum_1week'),
            'momentum_change_1week': data.get('momentum_change_1week'),
            'volume_momentum_1week': data.get('volume_momentum_1week'),
            'volume_momentum_change_1week': data.get('volume_momentum_change_1week'),   
            
            'volatility_1year': data.get('volatility_1year'),
            'momentum_1year': data.get('momentum_1year'),
            'momentum_change_1year': data.get('momentum_change_1year'),
            'volume_momentum_1year': data.get('volume_momentum_1year'),
            'volume_momentum_change_1year': data.get('volume_momentum_change_1year'),
            
            'volatility_ytd': data.get('volatility_ytd'),
            'momentum_ytd': data.get('momentum_ytd'),
            'momentum_change_ytd': data.get('momentum_change_ytd'),
            'volume_momentum_ytd': data.get('volume_momentum_ytd'),
            'volume_momentum_change_ytd': data.get('volume_momentum_change_ytd'),
            
            'volatility_24hr': data.get('volatility_24hr'),
            'momentum_24hr': data.get('momentum_24hr'),
            'momentum_change_24hr': data.get('momentum_change_24hr'),
            'volume_momentum_24hr': data.get('volume_momentum_24hr'),
            'volume_momentum_change_24hr': data.get('volume_momentum_change_24hr'),
        }
    else:
        # Handle the case when data is not available for the symbol
        return {
            'company': stock.company,
            'symbol': stock.symbol,
            'sector': stock.sector,
            'current_price': 0,
            "percent_change": 0,
            'change': 0,
        }

def handle_special_values(value):
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return 0  # or any default value you prefer
    return value


def get_details3(stocks):
    symbols =[stock.symbol for stock in stocks]
    stockdata= get_stockdata2()
    # print(stockdata)
    # return [get_details2(stock,stockdata) for stock in stocks]
    with ThreadPoolExecutor() as executor:
            futures = [executor.submit(get_details2, stock,stockdata) for stock in stocks]
            performance_data = [future.result() for future in futures]
    return performance_data

def get_alert_data(prompt):
    client = OpenAI()

    model = '''
    class Alert(auto_prefetch.Model):
        user= auto_prefetch.ForeignKey(User,on_delete=models.CASCADE)
        stock= auto_prefetch.ForeignKey(Stock,on_delete=models.CASCADE)
        alert_name=models.CharField(max_length=50)
        description=models.TextField(default="")
        alert_type=models.CharField(max_length=30, choices=(("price", "price"), ("volume", "volume")), default='price')
        action=models.CharField(max_length=50, choices=(("above", "above"), ("below", "below")))
        to_price=models.FloatField(blank=True, null=True)
        to_volume=models.FloatField(blank=True, null=True)    
        frequency=models.CharField(max_length=50, choices=(("Once","Once"),("Everytime", "Everytime")))
        expire = models.DateTimeField(default=datetime.now() +timedelta(weeks=7))
        
    '''
    # prompt = '''
    # notify me for ZENITHBANK stock everytime the volume goes below 9320 before 7 january 2024 3pm
    # '''
    # prompt = '''
    # alert me everytime WEMABANK price goes below 93.20 before 7 january 2024 3pm
    # '''

    response = client.chat.completions.create(
    model="gpt-3.5-turbo",
    messages=[
        {"role": "system", "content": "You are a helpful django software development assistant helping in creating a trading app alert system."},
        {"role": "user", "content": f'''i have company name and symbol pairing {pairs} useful for getting appropriate symbol that will be value of "stocks".
         i want to extract parameters from - {prompt} - to create djano model {model} can you 
            extract the needed parameter in python dictionary  format only as the response, the expected dict keys are stock,alert_type,action,to_price or to_volume and frequency. if there is no element of frequency in  the text, then "frequency":"Once".
            don't write write any explanation before or after the dictionary,all keys and values must be string and in double quotation marks. I only want the dictionary as response, nothing else, dont explain anything even if you made assumptions'''}
    ]
    )


    # print(response)
    # print(response['choices'][0]['message']['content'])
    return response.choices[0].message.content


from channels.db import database_sync_to_async

@database_sync_to_async
def get_alert_prompt_history(id):
    user =User.objects.get(id=id)
    
    alerts_query= AlertAI.objects.filter(user=user, alert_created=True)
    if alerts_query:
        alerts =[(alert.prompt, alert.created.isoformat()) for alert in alerts_query]
        alerts_sorted = sorted(alerts, key=lambda x: x[1], reverse=True)
        return alerts_sorted
    
@database_sync_to_async
def get_conversation(name, user):
    conversation,created = Conversation.objects.get_or_create(name=name, user=user)
    if created:
        client = OpenAI()
        thread = client.beta.threads.create()
        conversation.thread_id = thread.id
        conversation.save()
    return conversation

@database_sync_to_async
def get_messages(conversation):
    messages= Message.objects.filter(room = conversation)
    return messages

from django.utils import timezone

def get_alerts(user):
    
    current_month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    current_month_end = current_month_start.replace(month=current_month_start.month + 1) - timezone.timedelta(seconds=1)

    alerts_query = Alert.objects.filter(
        created__range=(current_month_start, current_month_end), user=user
    )
    alerts = AlertSerializer(alerts_query, many=True).data
    print('serialize',alerts)
    return alerts
    