import pytz
from pymongo import MongoClient
from datetime import datetime
from django.core.management.base import BaseCommand
import os

def remove_items_if_timestamp_matches(collection, target_timestamp):
    # Find the document to update
    existing_document = collection.find_one()

    if existing_document:
        # Check if the last timestamp matches the target timestamp
        if 't' in existing_document and existing_document['t']:
            last_timestamp = existing_document['t'][-1]
            # print(f"Last timestamp: {last_timestamp}")
            # if last_timestamp > target_timestamp:
            #     # Remove the last item from each list if the timestamp matches
            #     for key in ['t', 'o', 'h', 'l', 'c', 'v']:
            #         if key in existing_document and existing_document[key]:
            #             existing_document[key] = existing_document[key][:-1]

            #     # Update the document in the collection
            #     # collection.update_one({"_id": existing_document['_id']}, {"$set": existing_document})

            #     print(f"Updated document by removing items with timestamp {target_timestamp}.")
            # else:
            #     print(f"Last timestamp does not match {target_timestamp}.")
            for key in ['t', 'o', 'h', 'l', 'c', 'v']:
                if key in existing_document and existing_document[key]:
                    existing_document[key] = existing_document[key][:-1]

            # Update the document in the collection
            collection.update_one({"_id": existing_document['_id']}, {"$set": existing_document})

            print(f"Updated document by removing items with timestamp {target_timestamp}.")

            # Update the document in the collection
            # collec
        else:
            print(f"No timestamp found in document.")
    else:
        print(f"No document found.")

class Command(BaseCommand):
    help = 'Remove last items from lists if the timestamp matches a specific value'

    def handle(self, *args, **kwargs):
        # Connect to MongoDB
        client = MongoClient(os.environ.get('MONGO_STRING'),tls=True, tlsAllowInvalidCertificates=True)
        db = client['chartdata_1D']
        
        # Set the target timestamp to Lagos time
        lagos_tz = pytz.timezone('Africa/Lagos')
        target_timestamp = lagos_tz.localize(datetime(2024, 6, 28, 14, 25)).timestamp()
        print(f"Target timestamp: {target_timestamp}")
        
        # List all collection names
        collection_names = db.list_collection_names()
        print(len(collection_names))

        # Iterate through each collection
        for symbol in collection_names:
            print(symbol)
            collection = db[symbol]
            remove_items_if_timestamp_matches(collection, target_timestamp)
