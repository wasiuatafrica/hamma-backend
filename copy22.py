import boto3
from boto3.dynamodb.conditions import Key
import os
from datetime import datetime

# Add your AWS credentials
aws_access_key_id = 'AKIASIVIZUMNWPBDU5XA'
aws_secret_access_key = 'Ef+LxjiA/OPKPD5nY6iDaP3qDaexF/QhmUEuR99w'
region_name = 'eu-north-1'  # Specify your AWS region

# Initialize a session using Amazon DynamoDB with provided credentials
session = boto3.Session(
    aws_access_key_id=aws_access_key_id,
    aws_secret_access_key=aws_secret_access_key,
    region_name=region_name
)

# Initialize DynamoDB resource
dynamodb = session.resource('dynamodb')

# Specify the source and destination table names
source_table_name = 'main2'
destination_table_name = 'main3'

# Get the source and destination tables
source_table = dynamodb.Table(source_table_name)
destination_table = dynamodb.Table(destination_table_name)

def copy_data_to_new_table():
    # Scan the source table
    response = source_table.scan()

    # Get the items
    items = response['Items']

    # Iterate over the items
    for item in items:
        # Add the sort key to the item (if necessary, modify this to suit your sort key)
        # item['sort_key'] = 'your_sort_key_value'  # Replace with your sort key logic

        # Write the item to the destination table
        destination_table.put_item(Item=item)

    print(f"Data copied from {source_table_name} to {destination_table_name}")

# Call the function to start copying data
copy_data_to_new_table()
