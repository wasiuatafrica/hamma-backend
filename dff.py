import requests 

url = "https://api.paystack.co/transaction"
headers = {"Authorization": "Bearer sk_live_59c15f8ea814ea5dbe33a13b7a400ed9587aa033"}

response = requests.get(url, headers=headers)

# Check the status code of the response
if response.status_code == 200:
    # Process the response content
    # print(response.json()['data'][10])
    data = response.json()['data'][0]
    print(data)
    # for trans in data:
    #     print(f"{trans['amount']},{trans['status']}, {trans['channel']}, {trans['created_at']}, {trans['customer']['email']},{trans['customer']['first_name']}, {trans['metadata']}, {trans['source']}" )
    #     print('----------------------------')
else:
    # Handle the error
    print(f"Error: {response.status_code}\n{response.text}")
