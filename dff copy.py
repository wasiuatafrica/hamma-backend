import requests 

url = "https://api.paystack.co/terminal/Vt_sq95w9jy/presence"
headers = {"Authorization": "Bearer sk_live_59c15f8ea814ea5dbe33a13b7a400ed9587aa033"}

response = requests.get(url, headers=headers)

# Check the status code of the response
if response.status_code == 200:
    # Process the response content
    print(response.json())
else:
    # Handle the error
    print(f"Error: {response.status_code}\n{response.text}")
