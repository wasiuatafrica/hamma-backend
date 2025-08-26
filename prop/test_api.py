#!/usr/bin/env python3
"""
Test script for the new PropAccountDataView API endpoint
This demonstrates how to generate the required signature and make the API call
"""

import hashlib
import time
import requests
import json


def generate_signature(email, secret_key):
    """Generate signature for API authentication"""
    message = f"{email}"
    signature = hashlib.sha256(f"{message}:{secret_key}".encode()).hexdigest()
    return signature


def test_prop_account_data_api():
    """Test the prop account data API endpoint"""

    # Configuration
    base_url = "http://localhost:8000"  # Adjust to your server URL
    endpoint = "/prop/account-data/"
    email = "user@example.com"  # Replace with actual email
    secret_key = "your_secret_key_here"  # Replace with actual secret key

    # Generate signature
    signature = generate_signature(email, secret_key)

    # Prepare headers
    headers = {
        "Content-Type": "application/json",
        "X-Signature": signature,
    }

    # Prepare request data
    data = {"email": email}

    # Make the API call
    try:
        response = requests.post(f"{base_url}{endpoint}", headers=headers, json=data)

        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")

        if response.status_code == 200:
            result = response.json()
            print(f"Success! Found {result.get('total_accounts', 0)} accounts")
            print(f"User: {result.get('user_fullname', 'N/A')}")
            print(f"Last Updated: {result.get('last_updated', 'N/A')}")

            # Print account details
            for i, account in enumerate(result.get("accounts", []), 1):
                print(f"\nAccount {i}:")
                print(f"  ID: {account.get('account_id', 'N/A')}")
                print(f"  Model: {account.get('model_type', 'N/A')}")
                print(f"  Type Level: {account.get('account_type_level', 'N/A')}")
                print(f"  Profit: {account.get('current_percentage_profit', 0)}%")
                print(f"  Balance: {account.get('current_balance', 0)}")
                print(f"  Equity: {account.get('current_equity', 0)}")
                print(f"  Blown: {account.get('blown', False)}")
                print(f"  Inactive: {account.get('inactive_by_inactivity', False)}")
                print(f"  Trading Days: {account.get('trading_days', 0)}")

        else:
            print(f"Error: {response.text}")

    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
    except json.JSONDecodeError as e:
        print(f"Failed to parse JSON response: {e}")


if __name__ == "__main__":
    print("Testing Prop Account Data API...")
    print("=" * 50)
    test_prop_account_data_api()
