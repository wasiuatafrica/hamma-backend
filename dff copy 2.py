import requests 

id = 3504898227
# id = 3504782924
url = f"https://api.paystack.co/transaction/{id}"
headers = {"Authorization": "Bearer "}

response = requests.get(url, headers=headers)

# Check the status code of the response
if response.status_code == 200:
    # Process the response content
    # print(response.json()['data'][10])
    data = response.json()['data']['authorization']['narration']
    dat3 = response.json()['data']['authorization']
    data2 = response.json()['data']
    data1 = data.split('/')
    print(data)
    print(data1)
    # for trans in data:
    #     print(f"{trans['amount']},{trans['status']}, {trans['channel']}, {trans['created_at']}, {trans['customer']['email']},{trans['customer']['first_name']}, {trans['metadata']}, {trans['source']}" )
    #     print('----------------------------')
else:
    # Handle the error
    print(f"Error: {response.status_code}\n{response.text}")
