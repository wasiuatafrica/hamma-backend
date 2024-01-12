# notifications/management/commands/delete_old_notifications.py
from django.core.management.base import BaseCommand
from django.conf import settings
import boto3
from datetime import datetime

class Command(BaseCommand):
    help = 'Delete old notifications in DynamoDB'

    def handle(self, *args, **options):
        dynamodb = boto3.resource('dynamodb', region_name='eu-north-1')
        table_name = 'Anyon'
        table = dynamodb.Table(table_name)
        
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
            return notifications
        
        # Get all user_ids
        user_ids = set()

        # Fetch all user_ids from the DynamoDB table
        response = table.scan(ProjectionExpression='user_id')
        for item in response.get('Items', []):
            user_ids.add(item['user_id'])

        print(user_ids)
        # Iterate through each user_id
        for user_id in user_ids:
            # Fetch notifications for the user_id
            notifications = get_notifications(user_id)

            # Sort notifications by timestamp
            notifications.sort(key=lambda x: x['timestamp'], reverse=True)

            # Keep the latest 3 notifications
            notifications_to_keep = notifications[:3]

            # Delete the rest of the notifications
            notifications_to_delete = notifications[3:]
            for notification in notifications_to_delete:
                table.delete_item(
                    Key={
                        'user_id': str(user_id),
                        'notification_id': notification['notification_id']
                    }
                )
                print(f"Deleted notification {notification['notification_id']} for user {user_id}")

            print(f"Kept the latest 3 notifications for user {user_id}")

