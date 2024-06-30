import json
import os
import pytz
import pandas as pd
from datetime import datetime
from pymongo import MongoClient
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    # Extract symbol from the event
    symbol = event['symbol']
    
    # Setup MongoDB connection
    MONGO_URL = os.environ['MONGO_STRING']
    mongo_client = MongoClient(MONGO_URL, tls=True, tlsAllowInvalidCertificates=True)
    db_merged = mongo_client["livelake3"]
    collection_merged = db_merged["merged_live_price"]
    
    lagos_tz = pytz.timezone("Africa/Lagos")
    today = datetime.now(lagos_tz).date()
    
    pipeline = [
        {
            "$project": {
                "_id": 0,
                "documents": {
                    "$objectToArray": "$$ROOT"
                }
            }
        },
        {
            "$unwind": "$documents"
        },
        {
            "$match": {
                "$expr": {
                    "$eq": [
                        {
                            "$dateToString": {
                                "format": "%Y-%m-%d",
                                "date": {
                                    "$toDate": "$documents.v.datetime"
                                },
                                "timezone": "Africa/Lagos"
                            }
                        },
                        today.strftime("%Y-%m-%d")
                    ]
                },
                "documents.k": symbol  # Match documents for the given symbol only
            }
        },
        {
            "$replaceRoot": {
                "newRoot": "$documents.v"
            }
        }
    ]

    cursor = collection_merged.aggregate(pipeline)
    data = list(cursor)
    
    if not data:
        return {
            'statusCode': 200,
            'body': json.dumps(f"No data found for symbol {symbol} on {today}")
        }
    
    df = pd.DataFrame(data)
    df.drop(["change", "percentage_change", "current_price", "volatility", "momentum"], axis=1, inplace=True)
    df['timestamp'] = pd.to_datetime(df['datetime']).apply(lambda dt: dt.timestamp())
    df_filtered = df.sort_values(['symbol', 'timestamp'])
    df_filtered['volume_diff'] = df_filtered['volume'].diff()
    df_filtered = df_filtered[df_filtered['volume_diff'] != 0]
    df_filtered.dropna(inplace=True)
    
    new_data = {
        "t": df_filtered["timestamp"].tolist(), 
        "o": df_filtered["open"].tolist(),  
        "h": df_filtered["high"].tolist(),  
        "l": df_filtered["low"].tolist(),  
        "c": df_filtered["close"].tolist(),  
        "v": df_filtered["volume_diff"].tolist(), 
    }

    update_document(symbol, 'chartdata_5', new_data)
    
    return {
        'statusCode': 200,
        'body': json.dumps(f"Updated data for symbol {symbol}")
    }

def update_document(symbol, dbase, new_data):
    mongo_client = MongoClient(os.environ['MONGO_STRING'], tls=True, tlsAllowInvalidCertificates=True)
    db = mongo_client[dbase]
    
    if symbol not in db.list_collection_names():
        db.create_collection(symbol)
    
    collection = db[symbol]
    existing_document = collection.find_one()
    
    if existing_document:
        id = existing_document['_id']
        for key in ['t', 'o', 'h', 'l', 'c', 'v']:
            if key in new_data:
                if key in existing_document:
                    existing_document[key].extend(new_data[key])
                else:
                    existing_document[key] = new_data[key]
        collection.update_one({"_id": id}, {"$set": existing_document})
        logger.info(f"{symbol} updated")
   
