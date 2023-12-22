import uuid
from django.core.mail import send_mail
from pymongo import MongoClient
import json
from bson import ObjectId
from bson import json_util

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