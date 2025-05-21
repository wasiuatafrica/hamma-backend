# external_trading/views.py
import json
import time
from datetime import date, datetime
from decimal import Decimal

from django.contrib.auth import authenticate
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from execution.models import DemoPortfolio
from portfolio.utils import get_price, get_stockdata2

from .models import (
    ApiKey,
    ExternalConnection,
    ExternalPlatformPermission,
    ExternalTradingLog,
    PlatformType,
)
from .serializers import (
    ApiKeySerializer,
    ExternalConnectionSerializer,
    ExternalPlatformPermissionSerializer,
)
from .services.api_key_service import ApiKeyService
from .services.trading_service import TradingService


class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return super().default(obj)


class ExternalConnectionViewSet(viewsets.ModelViewSet):
    serializer_class = ExternalConnectionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ExternalConnection.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=["post"])
    def generate_api_key(self, request, pk=None):
        """Generate a new API key for this connection"""
        try:
            connection = self.get_object()
            expires_in_days = request.data.get("expires_in_days")

            api_key = ApiKeyService.create_api_key(
                connection_id=connection.id, expires_in_days=expires_in_days
            )

            serializer = ApiKeySerializer(api_key, context={"show_secret": True})
            return Response(serializer.data)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"])
    def revoke_api_key(self, request, pk=None):
        """Revoke an API key"""
        key_id = request.data.get("key_id")
        if not key_id:
            return Response(
                {"error": "key_id is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        connection = self.get_object()
        try:
            key = ApiKey.objects.get(key_id=key_id, connection=connection)
            key.is_active = False
            key.save()
            return Response({"message": "API key revoked successfully"})
        except ApiKey.DoesNotExist:
            return Response(
                {"error": "API key not found"}, status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=True, methods=["delete"])
    def delete_connection(self, request, pk=None):
        """Delete an external connection"""
        try:
            connection = self.get_object()
            connection.delete()
            return Response(
                {"message": "Connection deleted successfully."},
                status=status.HTTP_204_NO_CONTENT,
            )
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class DeleteConnectionView(APIView):
    permission_classes = []  # No DRF permissions as we use custom auth

    def _authenticate(self, request):
        """Authenticate the API request"""
        api_key = request.headers.get("X-API-Key")
        signature = request.headers.get("X-Signature")
        timestamp = request.headers.get("X-Timestamp")

        if not all([api_key, signature, timestamp]):
            return False, None, "Missing authentication headers"

        # Get request body as string
        body = ""

        # Validate the request
        is_valid, connection, message = ApiKeyService.validate_request(
            api_key=api_key,
            signature=signature,
            timestamp=timestamp,
            payload=body,
            request_path=request.path,
        )

        return is_valid, connection, message

    def delete(self, request):
        """Get all available accounts for the authenticated connection"""
        # Authenticate request
        print(request.body)
        is_valid, connection, message = self._authenticate(request)
        print(message)
        if not is_valid:
            return Response({"error": message}, status=status.HTTP_401_UNAUTHORIZED)

        connection = ExternalConnection.objects.filter(user=connection.user).first()
        if not connection:
            return Response(
                {"error": "No connection found for this user."},
                status=status.HTTP_404_NOT_FOUND,
            )
        connection.delete()
        return Response(
            {"message": "Connection deleted successfully."},
            status=status.HTTP_204_NO_CONTENT,
        )


class AuthenticateAndConnect(APIView):
    """
    Authenticate a user with email/password and create a connection
    for external platform use in one step.
    """

    permission_classes = []  # No authentication required for this endpoint

    @transaction.atomic
    def post(self, request):
        """Authenticate user and create a connection in one step"""
        email = request.data.get("email")
        password = request.data.get("password")
        platform_type = request.data.get("platform_type")
        name = request.data.get("name", f"{platform_type} Connection")

        # Validate input
        if not all([email, password, platform_type]):
            return Response(
                {"error": "Email, password, and platform_type are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check if platform type is valid
        if platform_type not in dict(PlatformType.choices).keys():
            return Response(
                {
                    "error": f"Invalid platform type. Options are: {', '.join(dict(PlatformType.choices).keys())}"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Authenticate the user
        user = authenticate(username=email, password=password)
        if not user:
            return Response(
                {"error": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED
            )

        try:
            # Create connection
            connection = ExternalConnection.objects.create(
                user=user, platform_type=platform_type, name=name
            )

            # Create default permissions
            ExternalPlatformPermission.objects.create(
                connection=connection,
                can_view_positions=True,
                can_open_trades=True,
                can_close_trades=False,
            )

            # Generate API key
            api_key = ApiKey.objects.create(connection=connection)

            # Return connection and API credentials
            connection_serializer = ExternalConnectionSerializer(connection)
            api_key_serializer = ApiKeySerializer(
                api_key, context={"show_secret": True}
            )

            response_data = {
                "connection": connection_serializer.data,
                "api_credentials": api_key_serializer.data,
                "user": {"email": user.email, "id": user.id},
            }

            return Response(response_data, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response(
                {"error": f"Failed to create connection: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ConnectionAccountsView(APIView):
    """View to list all available trading accounts for a connection"""

    permission_classes = []  # No DRF permissions as we use custom auth

    def _authenticate(self, request):
        """Authenticate the API request"""
        api_key = request.headers.get("X-API-Key")
        signature = request.headers.get("X-Signature")
        timestamp = request.headers.get("X-Timestamp")

        if not all([api_key, signature, timestamp]):
            return False, None, "Missing authentication headers"

        # Get request body as string
        body = request.body.decode("utf-8") if request.body else ""

        # Validate the request
        is_valid, connection, message = ApiKeyService.validate_request(
            api_key=api_key,
            signature=signature,
            timestamp=timestamp,
            payload=body,
            request_path=request.path,
        )

        return is_valid, connection, message

    def get(self, request):
        """Get all available accounts for the authenticated connection"""
        # Authenticate request
        is_valid, connection, message = self._authenticate(request)
        if not is_valid:
            return Response({"error": message}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            # Get user's demo portfolios
            demo_portfolios = DemoPortfolio.objects.filter(
                user=connection.user, can_trade=True, is_prop=False
            ).values("id", "account_name", "account_id", "balance")

            # Get user's competition portfolios

            # Prepare response
            accounts = {"demo_portfolios": list(demo_portfolios)}

            # Add account_type field to each account
            for account in accounts["demo_portfolios"]:
                account["account_type"] = "demo_portfolio"

            return Response(accounts)

        except Exception as e:
            return Response(
                {"error": f"Failed to retrieve accounts: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ExternalTradeAPI(APIView):
    permission_classes = []  # No DRF permissions as we use custom auth

    def _log_request(
        self,
        connection,
        action,
        request,
        response_data=None,
        status="success",
        error_message=None,
    ):
        """Log the external API request"""
        # Get client IP
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip = x_forwarded_for.split(",")[0]
        else:
            ip = request.META.get("REMOTE_ADDR")

        # Create log entry
        ExternalTradingLog.objects.create(
            connection=connection,
            action=action,
            ip_address=ip,
            request_data=request.data,
            response_data=response_data,
            status=status,
            error_message=error_message,
        )

    def _authenticate(self, request):
        """Authenticate the API request"""
        api_key = request.headers.get("X-API-Key")
        signature = request.headers.get("X-Signature")
        timestamp = request.headers.get("X-Timestamp")

        if not all([api_key, signature, timestamp]):
            return False, None, "Missing authentication headers"

        # Get request body as string
        body = request.body.decode("utf-8") if request.body else ""

        # Validate the request
        is_valid, connection, message = ApiKeyService.validate_request(
            api_key=api_key,
            signature=signature,
            timestamp=timestamp,
            payload=body,
            request_path=request.path,
        )

        return is_valid, connection, message

    def get(self, request, account_type, account_id, format=None):
        """Get open positions"""
        # Authenticate request
        is_valid, connection, message = self._authenticate(request)
        if not is_valid:
            return Response({"error": message}, status=status.HTTP_401_UNAUTHORIZED)

        # Check permissions
        if not connection.permissions.can_view_positions:
            self._log_request(
                connection,
                "view_positions",
                request,
                status="failed",
                error_message="Permission denied",
            )
            return Response(
                {"error": "This connection does not have permission to view positions"},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            # Get the portfolio using the trading service
            portfolio, _ = TradingService.get_account(
                account_type=account_type, account_id=account_id, user=connection.user
            )

            # Get open positions
            position_data = TradingService.get_open_positions(portfolio)

            serialized_data = json.loads(
                json.dumps(position_data, cls=CustomJSONEncoder)
            )

            # Log successful request
            self._log_request(connection, "view_positions", request, serialized_data)

            return Response(serialized_data)

        except ValidationError as e:
            print(e)
            # Log failed request
            self._log_request(
                connection,
                "view_positions",
                request,
                status="failed",
                error_message=str(e),
            )
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            print(e)
            # Log failed request
            self._log_request(
                connection,
                "view_positions",
                request,
                status="failed",
                error_message=str(e),
            )
            return Response(
                {"error": "An unexpected error occurred"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request, account_type, account_id, format=None):
        """Open a new trade"""
        # Authenticate request
        is_valid, connection, message = self._authenticate(request)
        if not is_valid:
            return Response({"error": message}, status=status.HTTP_401_UNAUTHORIZED)
        print(request.data)

        # Check permissions
        if not connection.permissions.can_open_trades:
            self._log_request(
                connection,
                "open_trade",
                request,
                status="failed",
                error_message="Permission denied",
            )
            return Response(
                {"error": "This connection does not have permission to open trades"},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            # Validate input parameters
            symbol = request.data.get("symbol")
            quantity = int(request.data.get("quantity", 0))
            action = request.data.get("action")
            order_type = request.data.get("order_type", "market")

            take_profit = request.data.get("take_profit")
            if take_profit in ("", None):
                take_profit = None
            stop_loss = request.data.get("stop_loss")
            if stop_loss in ("", None):
                stop_loss = None

            price = request.data.get("price") if order_type == "limit" else None
            order_id = request.data.get("order_id", f"ext-{int(time.time())}")
            time_in_force = request.data.get("time_in_force", "day")

            # # Restrict market orders to 10am-2:30pm Mon-Fri only (Lagos time)
            # if order_type == "market":
            #     import pytz

            #     lagos_tz = pytz.timezone("Africa/Lagos")
            #     now = timezone.now().astimezone(lagos_tz)
            #     # 0=Monday, 4=Friday
            #     if now.weekday() > 4 or not (
            #         now.hour > 9
            #         and (now.hour < 14 or (now.hour == 14 and now.minute <= 30))
            #     ):
            #         raise ValidationError(
            #             "Market orders are only allowed between 10:00am and 2:30pm, Monday to Friday (Lagos time)."
            #         )

            # Check allowed symbols if configured
            if (
                connection.permissions.allowed_symbols
                and symbol not in connection.permissions.allowed_symbols
            ):
                raise ValidationError(
                    "Trading %s is not allowed for this connection" % symbol
                )

            # Check max trade size if configured
            if connection.permissions.max_trade_size:
                current_price = float(get_price(symbol)["current_price"])
                trade_value = quantity * current_price
                if trade_value > float(connection.permissions.max_trade_size):
                    raise ValidationError("Trade size exceeds maximum allowed value")

            # Check max daily trades if configured
            if connection.permissions.max_daily_trades:
                today_start = timezone.now().replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                today_trades = ExternalTradingLog.objects.filter(
                    connection=connection,
                    action="open_trade",
                    status="success",
                    timestamp__gte=today_start,
                ).count()

                if today_trades >= connection.permissions.max_daily_trades:
                    raise ValidationError("Daily trade limit reached")

            # Get the portfolio using the trading service
            portfolio, _ = TradingService.get_account(
                account_type=account_type, account_id=account_id, user=connection.user
            )

            # Process the trade using the trading service
            if order_type == "market":
                position = TradingService.process_market_order(
                    portfolio=portfolio,
                    symbol=symbol,
                    quantity=quantity,
                    action=action,
                    order_id=order_id,
                    take_profit=take_profit,
                    stop_loss=stop_loss,
                    device_type="external_platform",
                )

                current_price = position.open_price
                response_data = {
                    "message": f"{action.title()} order placed successfully.",
                    "position_id": position.id,
                    "price": float(current_price),
                    "quantity": quantity,
                    "stock": symbol,
                }
                print(response_data)

            elif order_type == "limit":
                position = TradingService.process_limit_order(
                    portfolio=portfolio,
                    symbol=symbol,
                    quantity=quantity,
                    price=float(price),
                    action=action,
                    order_id=order_id,
                    take_profit=take_profit,
                    stop_loss=stop_loss,
                    time_in_force=time_in_force,
                    device_type="external_platform",
                )

                response_data = {
                    "message": f"{action.title()} limit order placed successfully.",
                    "position_id": position.id,
                    "limit_price": float(price),
                    "quantity": quantity,
                    "stock": symbol,
                }
            else:
                raise ValidationError("Invalid order type")

            # Log successful request
            self._log_request(connection, "open_trade", request, response_data)

            return Response(response_data, status=status.HTTP_201_CREATED)

        except ValidationError as e:
            # Log failed request
            self._log_request(
                connection, "open_trade", request, status="failed", error_message=str(e)
            )
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            print(e)
            # Log failed request
            self._log_request(
                connection, "open_trade", request, status="failed", error_message=str(e)
            )
            return Response(
                {"error": "An unexpected error occurred"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def delete(self, request, account_type, account_id, position_id, format=None):
        """Close an existing trade"""
        # Authenticate request
        is_valid, connection, message = self._authenticate(request)
        if not is_valid:
            return Response({"error": message}, status=status.HTTP_401_UNAUTHORIZED)

        # Check permissions
        if not connection.permissions.can_close_trades:
            self._log_request(
                connection,
                "close_trade",
                request,
                status="failed",
                error_message="Permission denied",
            )
            return Response(
                {"error": "This connection does not have permission to close trades"},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            # Get the portfolio using the trading service
            portfolio, _ = TradingService.get_account(
                account_type=account_type, account_id=account_id, user=connection.user
            )

            # Close the trade using the trading service
            trade_data = TradingService.close_trade(
                portfolio=portfolio, position_id=position_id
            )

            # Log successful request
            self._log_request(connection, "close_trade", request, trade_data)

            return Response(trade_data)

        except ValidationError as e:
            # Log failed request
            self._log_request(
                connection,
                "close_trade",
                request,
                status="failed",
                error_message=str(e),
            )
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            # Log failed request
            print(str(e))
            self._log_request(
                connection,
                "delete_connection",
                request,
                status="failed",
                error_message=str(e),
            )
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def put(self, request, account_type, account_id, format=None):
        """Close all trades for an account"""
        # Authenticate request
        is_valid, connection, message = self._authenticate(request)
        if not is_valid:
            return Response({"error": message}, status=status.HTTP_401_UNAUTHORIZED)

        # Check permissions
        if not connection.permissions.can_close_trades:
            self._log_request(
                connection,
                "close_all_trades",
                request,
                status="failed",
                error_message="Permission denied",
            )
            return Response(
                {"error": "This connection does not have permission to close trades"},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            # Get the portfolio using the trading service
            portfolio, _ = TradingService.get_account(
                account_type=account_type, account_id=account_id, user=connection.user
            )

            # Close all trades using the trading service
            result = TradingService.close_all_trades(portfolio=portfolio)

            # Log successful request
            self._log_request(connection, "close_all_trades", request, result)

            return Response(result)

        except ValidationError as e:
            # Log failed request
            self._log_request(
                connection,
                "close_all_trades",
                request,
                status="failed",
                error_message=str(e),
            )
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            # Log failed request
            self._log_request(
                connection,
                "close_all_trades",
                request,
                status="failed",
                error_message=str(e),
            )
            return Response(
                {"error": "An unexpected error occurred"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class DeleteActionView(APIView):
    permission_classes = []  # Custom authentication

    def _authenticate(self, request):
        """Authenticate the API request (copied from ExternalTradeAPI)"""
        api_key = request.headers.get("X-API-Key")
        signature = request.headers.get("X-Signature")
        timestamp = request.headers.get("X-Timestamp")

        if not all([api_key, signature, timestamp]):
            return False, None, "Missing authentication headers"

        body = request.body.decode("utf-8") if request.body else ""
        # Ensure request.path is what you expect for signature.
        # For "/api/connection/action/", request.path should be exactly that.
        is_valid, connection, message = ApiKeyService.validate_request(
            api_key=api_key,
            signature=signature,
            timestamp=timestamp,
            payload=body,  # This will be the JSON string of {"action": "delete"}
            request_path=request.path,
        )
        return is_valid, connection, message

    def post(self, request, format=None):
        is_valid, connection_obj, message = self._authenticate(request)
        if not is_valid:
            # Optionally log auth failure here if connection_obj is None
            return Response(
                {"error": message, "message": message},
                status=status.HTTP_401_UNAUTHORIZED,
            )  # Added "message" for consistency

        if (
            not connection_obj
        ):  # Should be caught by is_valid=False, but good for defense
            return Response(
                {"error": "Authentication failed: Connection not found."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        action_to_perform = request.data.get("action")

        if action_to_perform == "delete_connection":
            try:

                connection_obj.delete()  # Delete the Hamma ExternalConnection

                return Response(
                    {"message": "Hamma connection deleted successfully"},
                    status=status.HTTP_200_OK,
                )
            except Exception as e:
                print(str(e))

                return Response(
                    {
                        "error": f"Failed to delete Hamma connection: {str(e)}",
                        "message": f"Failed to delete Hamma connection: {str(e)}",
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
        else:

            return Response(
                {
                    "error": f"Invalid action: {action_to_perform}",
                    "message": f"Invalid action: {action_to_perform}",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
