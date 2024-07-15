import json
import boto3
from django.core.management.base import BaseCommand
from concurrent.futures import ThreadPoolExecutor
from execution.tasks import update_live_1m_lambda

class Command(BaseCommand):
    help = 'Trigger the gen_data_test Lambda function 200 times concurrently'

    def handle(self, *args, **kwargs):
        update_live_1m_lambda()