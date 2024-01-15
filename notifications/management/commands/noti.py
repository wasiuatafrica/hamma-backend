# notifications/management/commands/delete_old_notifications.py
from django.core.management.base import BaseCommand
from django.conf import settings
import boto3
from datetime import datetime
from notifications.utils import save_and_send_notification

class Command(BaseCommand):
    help = 'Delete old notifications in DynamoDB'

    def handle(self, *args, **options):
        save_and_send_notification(2, 'hello')