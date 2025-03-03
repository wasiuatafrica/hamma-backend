from pymongo import MongoClient
import os
from dotenv import load_dotenv
import json
from datetime import datetime

load_dotenv()


MONGO_URL = os.environ.get("MONGO_URL")

client = MongoClient(MONGO_URL, tls=True, tlsAllowInvalidCertificates=True)

db = client["livelake3"]
collection = db["live_price_combined"]

last_item = collection.find_one(sort=[("_id", -1)])
if last_item and "_id" in last_item:
    last_item.pop("_id")

# Save the response to a JSON file before printing
if last_item:
    with open(
        f'last_live-{datetime.now().strftime("%Y-%m-%d_%H-%M-%S")}.json',
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(last_item, f, ensure_ascii=False, indent=4)

client.close()
