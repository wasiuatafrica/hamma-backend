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
client = MongoClient(MONGO_URL, tls=True, tlsAllowInvalidCertificates=True)


db_live = client["livelake3"]
collection_live = db_live["live_price_combined"]
collection_merged = db_live["merged_live_price"]

from pymongo import MongoClient
from bson import ObjectId

def delete_empty_documents(collection):
    # Query to find documents that only have '_id' field
    query = {"$expr": {"$eq": [{"$size": {"$objectToArray": "$$ROOT"}}, 1]}}
    print(query)
    
    # Execute the delete operation
    result = collection.delete_many(query)
    
    # Return the number of deleted documents
    return result.deleted_count


deleted_count = delete_empty_documents(collection_live)
print(f"Deleted {deleted_count} empty documents.")