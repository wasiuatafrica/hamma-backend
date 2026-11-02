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


        if response.status_code == 200:
            result = response.json()

            # Print account details
            for i, account in enumerate(result.get("accounts", []), 1):
                pass

        else:
            pass

    except requests.exceptions.RequestException as e:
        pass
    except json.JSONDecodeError as e:
        pass


if __name__ == "__main__":
    test_prop_account_data_api()
