import boto3
from botocore.exceptions import NoCredentialsError
from datetime import datetime
import shortuuid
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

channel_layer = get_channel_layer()

dynamodb = boto3.resource('dynamodb', region_name='eu-north-1')
table_name = 'Anyon'  
table = dynamodb.Table(table_name)

def save_and_send_notification(user_id, message):
    data = {
                'notification_id': notification_id,
                'user_id': str(user_id),
                'timestamp': datetime.now().isoformat(),
                'is_read': 'False',
                'message': message,
            }
    try:
        notification_id = shortuuid.uuid()
        # Create a new notification item in DynamoDB
        response = table.put_item(
            Item= data
        )
        print(f"Notification saved for user {user_id}")
        
        async_to_sync(channel_layer.group_send)(
            f'user_{user_id}',
            {
                'type': 'send_notification',
                'message': data,
            }
        )
    except NoCredentialsError:
        print("AWS credentials not found. Make sure to configure your AWS credentials.")

def get_notifications(user_id):
    response = table.query(
        KeyConditionExpression='user_id = :uid',
        FilterExpression='is_read = :ir',
        ExpressionAttributeValues={
            ':uid': str(user_id),
            ':ir': 'False', 
        }
    )

    notifications = response.get('Items', [])
    notifications.sort(key=lambda x: x['timestamp'], reverse=True)
    
    # notifications={"Glory":1, "Book":3}
    return notifications


def update_notification(user_id, notification_id):
    try:
        response = table.update_item(
            Key={
                'user_id': str(user_id), 
                'notification_id': notification_id 
            },  
            UpdateExpression='SET is_read = :ir',
            ExpressionAttributeValues={':ir': 'True'}
        )
        print(f"Notification {notification_id} marked as read")
    except NoCredentialsError:
        print("AWS credentials not found. Make sure to configure your AWS credentials.")


