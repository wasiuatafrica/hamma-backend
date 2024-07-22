#!/usr/bin/env python3

import datetime
import socket
import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

MONGO_URL = os.environ.get('MONGO_URL')
def main():
    # Get current time
    current_time = datetime.datetime.now()
    
    # Get hostname
    hostname = socket.gethostname()
    
    # Get IP address
    ip_address = socket.gethostbyname(hostname)
    
    # Create a document to insert
    log_document = {
        "timestamp": current_time,
        "hostname": hostname,
        "ip_address": ip_address
    }
    
    client = MongoClient(MONGO_URL, tls=True, tlsAllowInvalidCertificates=True)
    
    # Select the database and collection
    db = client['startup_logs']
    collection = db['instance_logs']
    
    # Insert the document
    result = collection.insert_one(log_document)
    
    # Print confirmation message
    print(f"Log inserted with ID: {result.inserted_id}")
    print(f"Script executed at {current_time} on {hostname} ({ip_address})")

if __name__ == "__main__":
    main()