# tasks.py
from celery import shared_task
import boto3
from boto3.dynamodb.conditions import Key, Attr
from .utils import table


@shared_task
def update_notifications_task(user_id):

    response = table.query(
        KeyConditionExpression="user_id = :uid",
        FilterExpression="is_read = :ir",
        ExpressionAttributeValues={
            ":uid": str(user_id),
            ":ir": "False",
        },
    )

    notifications = response.get("Items", [])
    print(f"Found {len(notifications)} unread notifications for user {user_id}")

    for notification in notifications:
        print(
            f"Updating notification {notification['notification_id']} for user {user_id}"
        )
        table.update_item(
            Key={
                "user_id": user_id,
                "notification_id": notification["notification_id"],
            },
            UpdateExpression="SET is_read = :ir",
            ExpressionAttributeValues={":ir": True},
        )
    print(f"Updated {len(notifications)} notifications for user {user_id}")

    return len(notifications)
