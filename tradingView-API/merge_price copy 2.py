from pymongo import MongoClient
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

MONGO_URL = os.environ.get('MONGO_URL')

# Connect to MongoDB
def connect_to_mongodb(db_name):
    client = MongoClient(MONGO_URL, tls=True, tlsAllowInvalidCertificates=True)
    db = client[db_name]
    return db

# Function to update close prices for "ABBEYBDS" to 1.50
def last1():
    db = connect_to_mongodb("livelake3")
    collection = db["merged_live_price"]
    last_item = collection.find_one(sort=[('_id', -1)])
    return last_item

last_item = last1()
needed_symbols = []
print(type(last_item))
for symbol,data in last_item.items():
    if symbol != "_id":
        if data['percentage_change'] and data['percentage_change'] > 10:
            needed_symbols.append(symbol)

print(needed_symbols)
