from pymongo import MongoClient
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

MONGO_URL = os.environ.get("MONGO_URL")

client = MongoClient(MONGO_URL, tls=True, tlsAllowInvalidCertificates=True)

db = client["startup_logs"]
collection = db["instance_logs"]

last_item = collection.find_one(sort=[("_id", -1)])
if last_item:
    formatted_date = last_item["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
    print({**last_item, "timestamp": formatted_date})
else:
    print("No records found")

client.close()
