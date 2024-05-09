
from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv()


MONGO_URL = os.environ.get('MONGO_URL')

client = MongoClient(MONGO_URL, tls=True, tlsAllowInvalidCertificates=True)

db = client['livelake3']  
collection = db['merged_live_price']  

last_item = collection.find_one(sort=[('_id', -1)]) 
print( last_item)

client.close()
