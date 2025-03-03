from pymongo import MongoClient
import os
import json
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

MONGO_URL = os.environ.get("MONGO_URL")

client = MongoClient(MONGO_URL, tls=True, tlsAllowInvalidCertificates=True)

db = client["livelake3"]
collection = db["merged_live_price"]

# Fetch the last item from the collection
last_item = collection.find_one(sort=[("_id", -1)])
if last_item and "_id" in last_item:
    last_item.pop("_id")

# Save the response to a JSON file before printing
if last_item:
    with open(
        f'last_item-{datetime.now().strftime("%Y-%m-%d_%H-%M-%S")}.json',
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(last_item, f, ensure_ascii=False, indent=4)

# Print the last item
print(last_item)

client.close()
