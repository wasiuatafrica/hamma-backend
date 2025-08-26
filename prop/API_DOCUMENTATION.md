# Prop Account Data API Documentation

## Overview
The Prop Account Data API endpoint provides detailed information about prop trading accounts for a specific user. This endpoint is designed for backend-to-backend communication and uses signature-based authentication instead of DRF authentication.

## Endpoint Details
- **URL**: `/prop/account-data/`
- **Method**: `POST`
- **Authentication**: Signature-based (no DRF auth required)

## Request Format

### Headers
- `Content-Type`: `application/json`
- `X-Signature`: SHA256 signature for authentication

### Request Body
```json
{
    "email": "user@example.com"
}
```

## Authentication

### Signature Generation
The signature is generated using the following formula:
```
message = email
signature = SHA256(message + ":" + secret_key)
```

### Python Example
```python
import hashlib

def generate_signature(email, secret_key):
    message = f"{email}"
    signature = hashlib.sha256(f"{message}:{secret_key}".encode()).hexdigest()
    return signature

# Usage
signature = generate_signature("user@example.com", "your_secret_key")
```

### Environment Variable
Set the secret key in your environment:
```bash
export PROP_API_SECRET_KEY="your_secure_secret_key_here"
```

## Response Format

### Success Response (200)
```json
{
    "user_email": "user@example.com",
    "user_fullname": "John Doe",
    "total_accounts": 2,
    "accounts": [
        {
            "account_id": "12345",
            "account_name": "My Trading Account",
            "model_type": "model_1",
            "account_type_level": "challenge",
            "current_percentage_profit": 5.25,
            "current_balance": 1052500.00,
            "current_equity": 1052500.00,
            "initial_balance": 1000000.00,
            "blown": false,
            "inactive_by_inactivity": false,
            "profit_target": 50000.00,
            "daily_loss_limit": 50000.00,
            "max_account_loss_limit": 200000.00,
            "trading_days": 8,
            "created_date": "2025-09-01",
            "is_active": true,
            "activated": true,
            "receipt_approved": true
        }
    ],
    "last_updated": "2025-09-15 14:30:25"
}
```

### Error Responses

#### 400 Bad Request
```json
{
    "error": "Email is required"
}
```

#### 401 Unauthorized
```json
{
    "error": "Invalid signature or expired request"
}
```

#### 404 Not Found
```json
{
    "error": "User not found"
}
```

#### 500 Internal Server Error
```json
{
    "error": "An unexpected error occurred"
}
```

## Account Data Fields

| Field | Type | Description |
|-------|------|-------------|
| `account_id` | string | Unique account identifier |
| `account_name` | string | User-defined account name |
| `model_type` | string | Trading model type (model_1, model_2) |
| `account_type_level` | string | Account level (challenge, funded, etc.) |
| `current_percentage_profit` | float | Current profit as percentage |
| `current_balance` | float | Current account balance |
| `current_equity` | float | Current account equity |
| `initial_balance` | float | Initial account balance |
| `blown` | boolean | Whether account has been blown |
| `inactive_by_inactivity` | boolean | Whether account is inactive due to inactivity |
| `profit_target` | float | Profit target amount |
| `daily_loss_limit` | float | Daily loss limit amount |
| `max_account_loss_limit` | float | Maximum account loss limit |
| `trading_days` | integer | Number of trading days |
| `created_date` | string | Account creation date (YYYY-MM-DD) |
| `is_active` | boolean | Whether account is active |
| `activated` | boolean | Whether account has been activated |
| `receipt_approved` | boolean | Whether payment receipt has been approved |

## Filtering
- Only returns prop accounts created after August 25, 2025
- Only returns accounts where `is_prop=True`
- Accounts are ordered by creation date (newest first)

## Rate Limiting & Security
- Signature verification prevents unauthorized access
- No rate limiting currently implemented (can be added if needed)

## Testing
Use the provided `test_api.py` script to test the endpoint:

```bash
# Install required packages
pip install requests

# Update the script with your configuration
# Run the test
python prop/test_api.py
```

## Testing with Postman

### 1. Basic Setup
**Method**: `POST`  
**URL**: `http://localhost:8000/prop/account-data/`

### 2. Headers Tab
Add these headers:
```
Content-Type: application/json
X-Signature: [your_generated_signature]
```

### 3. Body Tab
Select **raw** and **JSON**, then add:
```json
{
    "email": "user@example.com"
}
```

### 4. Generating the Signature

#### Option A: Use Pre-request Script
In the **Pre-request Script** tab:

```javascript
// Generate signature before request
const email = pm.request.body.raw;
const secretKey = pm.environment.get("secret_key") || "your_secret_key_here";

// Parse email from body
let emailValue;
try {
    const bodyData = JSON.parse(email);
    emailValue = bodyData.email;
} catch (e) {
    emailValue = "user@example.com"; // fallback
}

// Generate signature
const message = `${emailValue}`;
const signature = CryptoJS.SHA256(`${message}:${secretKey}`).toString();

// Set header
pm.request.headers.add({
    key: "X-Signature",
    value: signature
});

console.log("Generated signature:", signature);
```

#### Option B: Manual Calculation
Calculate signature manually using:
```bash
echo -n "user@example.com:your_secret_key" | sha256sum
```

### 5. Environment Variables
Create a Postman environment with:
```
secret_key: your_actual_secret_key_here
```

### 6. Test Response Validation
Add this to your **Tests** tab:

```javascript
// Test response structure
pm.test("Status code is 200", function () {
    pm.response.to.have.status(200);
});

pm.test("Response has required fields", function () {
    const jsonData = pm.response.json();
    pm.expect(jsonData).to.have.property('user_email');
    pm.expect(jsonData).to.have.property('total_accounts');
    pm.expect(jsonData).to.have.property('accounts');
    pm.expect(jsonData).to.have.property('last_updated');
});
```

## Integration Example

### cURL
```bash
#!/bin/bash

EMAIL="user@example.com"
SECRET_KEY="your_secret_key"
MESSAGE="${EMAIL}"
SIGNATURE=$(echo -n "${MESSAGE}:${SECRET_KEY}" | sha256sum | cut -d' ' -f1)

curl -X POST "http://localhost:8000/prop/account-data/" \
  -H "Content-Type: application/json" \
  -H "X-Signature: ${SIGNATURE}" \
  -d "{\"email\": \"${EMAIL}\"}"
```

### JavaScript/Node.js
```javascript
const crypto = require('crypto');

function generateSignature(email, secretKey) {
    const message = `${email}`;
    return crypto.createHash('sha256').update(`${message}:${secretKey}`).digest('hex');
}

async function getPropAccountData(email, secretKey) {
    const signature = generateSignature(email, secretKey);
    
    const response = await fetch('http://localhost:8000/prop/account-data/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-Signature': signature
        },
        body: JSON.stringify({ email })
    });
    
    return response.json();
}
```
