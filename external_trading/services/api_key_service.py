# external_trading/services/api_key_service.py
import hmac
import hashlib
import time
from django.utils import timezone
from ..models import ApiKey, ExternalConnection, ExternalTradingLog


class ApiKeyService:
    @staticmethod
    def validate_request(api_key, signature, timestamp, payload, request_path):
        """
        Validate an API request using HMAC authentication
        """
        try:
            # Find the API key
            key_obj = ApiKey.objects.select_related("connection").get(
                api_key=api_key, is_active=True
            )

            # Check if key is expired
            if key_obj.is_expired():
                return False, None, "API key expired"

            # Validate the signature
            # Format: timestamp + request_path + payload
            message = f"{timestamp}{request_path}{payload}"
            expected_signature = hmac.new(
                key_obj.secret_key.encode(), message.encode(), hashlib.sha256
            ).hexdigest()

            if not hmac.compare_digest(signature, expected_signature):
                return False, None, "Invalid signature"

            # Check timestamp to prevent replay attacks (within 5 minutes)
            current_time = int(time.time())
            if abs(current_time - int(timestamp)) > 300:
                return False, None, "Request timestamp too old or from the future"

            # Update last used
            key_obj.update_last_used()

            return True, key_obj.connection, "Valid request"

        except ApiKey.DoesNotExist:
            return False, None, "Invalid API key"
        except Exception as e:
            return False, None, f"Authentication error: {str(e)}"

    @staticmethod
    def create_api_key(connection_id, expires_in_days=None):
        """
        Create a new API key for a connection
        """
        connection = ExternalConnection.objects.get(id=connection_id)

        # Set expiration date if provided
        expires_at = None
        if expires_in_days:
            expires_at = timezone.now() + timezone.timedelta(days=expires_in_days)

        api_key = ApiKey.objects.create(connection=connection, expires_at=expires_at)

        return api_key

    @staticmethod
    def revoke_api_key(key_id):
        """
        Revoke an API key
        """
        try:
            key = ApiKey.objects.get(key_id=key_id)
            key.is_active = False
            key.save()
            return True
        except ApiKey.DoesNotExist:
            return False
