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
def update_abbeybds_close():
    db = connect_to_mongodb("livelake3")
    collection = db["live_price_combined"]
    
    # Condition to find all documents with "ABBEYBDS" key
    condition = {"AFROMEDIA": {"$exists": True}}

    # Update operation to set 'ABBEYBDS.close' to 1.50
    update = {"$set": {"AFROMEDIA.close": 0.24}}

    # Execute the update
    result = collection.update_many(condition, update)

    # Return the number of documents that were updated
    return result.modified_count

# Call the function and print the result
updated_count = update_abbeybds_close()
print(f"Updated {updated_count} documents with 'close' price set to 2.50 for 'ABBEYBDS'")
