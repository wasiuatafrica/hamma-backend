import json
import pandas as pd
import numpy as np
from pymongo import MongoClient
from datetime import datetime, timedelta
import os

def generate_data(num_rows=1000):
    # Generate sample data
    dates = [datetime.now() - timedelta(days=i) for i in range(num_rows)]
    values = np.random.randint(1, 1000, num_rows)
    categories = np.random.choice(['A', 'B', 'C', 'D'], num_rows)
    
    # Create DataFrame
    df = pd.DataFrame({
        'date': dates,
        'value': values,
        'category': categories
    })
    
    return df.to_dict('records')

def lambda_handler(event, context):
    # Connect to MongoDB
    client = MongoClient(os.environ['MONGODB_URI'])
    db = client['lmabda_test']
    collection = db['mrrs']
    
    # Generate data
    data = generate_data()
    
    # Save data to MongoDB as a single document
    document = {
        'timestamp': datetime.now(),
        'data': data
    }
    collection.insert_one(document)
    
    