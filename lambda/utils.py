import boto3

lambda_client = boto3.client('lambda')

@shared_task
def invoke_update_live_1m(symbol):
    response = lambda_client.invoke(
        FunctionName='your_lambda_function_name',
        InvocationType='Event',  # Async invocation
        Payload=json.dumps({'symbol': symbol})
    )
    print(response)
