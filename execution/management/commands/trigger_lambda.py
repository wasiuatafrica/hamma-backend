import json
import boto3
from django.core.management.base import BaseCommand
from concurrent.futures import ThreadPoolExecutor

class Command(BaseCommand):
    help = 'Trigger the gen_data_test Lambda function 200 times concurrently'

    def handle(self, *args, **kwargs):
        # Initialize the boto3 client
        lambda_client = boto3.client('lambda',region_name='eu-north-1')

        # Prepare the event payload
        event_payload = {
            "symbols":  ["ASI", "ABBEYBDS", "ACADEMY", ]
        }

        def invoke_lambda(index):
            try:
                response = lambda_client.invoke(
                    FunctionName='gen_data_test',
                    InvocationType='Event',  # Async invocation
                    Payload=json.dumps(event_payload)
                )
                self.stdout.write(self.style.SUCCESS(f'Lambda function invoked successfully {index + 1} times'))
            except Exception as e:
                self.stderr.write(self.style.ERROR(f'Error invoking Lambda function at iteration {index + 1}: {e}'))

        # Use ThreadPoolExecutor to invoke the function concurrently
        with ThreadPoolExecutor() as executor:
            futures = [executor.submit(invoke_lambda, i) for i in range(200)]

            for future in futures:
                # This will block until each future is done and will raise exceptions if any occurred
                future.result()