import logging

import pandas as pd
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.core.mail import send_mail
from django.shortcuts import get_object_or_404, render
from rest_framework import generics, permissions, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from tvDatafeed import Interval, TvDatafeed

from . import serializers
from .models import ContactMessage, SupportMessage, SupportThread
from .serializers import ContactMessageSerializer

# Create your views here.

# Configure logging
logger = logging.getLogger(__name__)


class RateBotResponse(APIView):
    serializer_class = serializers.SupportMessageDisclaimerSerializer
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"detail": "Feedback recored, thank you."})
        return Response(serializer.errors, status.HTTP_400_BAD_REQUEST)


class SwitchBackToAIBot(APIView):
    permission_classes = [AllowAny]

    def put(self, request, thread):
        thread = get_object_or_404(SupportThread, id=thread)

        if not thread.switched_to_admin_support:
            return Response(
                {"detail": "Thread is already in AI bot mode."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        thread.switched_to_admin_support = False
        thread.save()

        welcome_message = self.create_welcome_back_message(thread)
        self.notify_chat_socket(welcome_message)

        return Response({"detail": "Chat switched back to ai bot successfully."})

    def create_welcome_back_message(self, thread):
        content = (
            "Welcome back to the AI assistant! I'm here to help you with any questions or concerns. "
            "Feel free to ask anything, and I'll do my best to assist you. "
            "If you need human support again, just let me know."
        )
        return SupportMessage.objects.create(
            thread=thread, sender="assistant", content=content
        )

    def notify_chat_socket(self, message):
        channel_layer = get_channel_layer()
        user_message_data = {
            "id": message.id,
            "sender": message.sender,
            "content": message.content,
            "fullname": message.name,
            "created": str(message.created),
            "updated": str(message.updated),
            "thread": message.thread.id,
            "user_name": message.user_name,
            "user_pics": str(message.user_pics),
            "thread_value": message.thread_value,
            "chat_switched_to_admin": message.thread.switched_to_admin_support,
        }

        async_to_sync(channel_layer.group_send)(
            f"email_{message.thread_value}_bot",
            {
                "type": "send_message_to_user",
                "message": user_message_data,  # Send the dictionary, not a JSON string
            },
        )


class MessageCreateView(generics.CreateAPIView):
    """
    API endpoint that allows users to submit a new contact message.
    Accessible by any user (authenticated or not).
    Handles POST requests.
    """

    queryset = ContactMessage.objects.all()  # Required for CreateAPIView
    serializer_class = ContactMessageSerializer
    permission_classes = [permissions.AllowAny]  # Allow anyone to submit a message

    def perform_create(self, serializer):
        # Save the contact message instance
        contact_message = serializer.save()

        # Send email to admin
        subject = f"New contact message from {contact_message.full_name}"
        message = f"""
        You have received a new contact message.

        Name: {contact_message.full_name}
        Email: {contact_message.email}
        Subject: {contact_message.subject}
        Message: {contact_message.message}
        """

        # You can set the 'from_email' as the sender's email, or use a default one like support@domain.com
        from_email = "Hamma Contact Message <hello@gohamma.com>"

        # Send email to admin
        send_mail(
            subject,
            message,
            from_email,
            [
                "traders@gohamma.com",
                "nexxyb@gmail.com",
            ],  # Add admin email(s) here or use a default from settings
            fail_silently=False,
        )


# --- View for Listing ALL Messages ---
class MessageListView(generics.ListAPIView):
    """
    API endpoint that allows listing all submitted contact messages.
    Accessible by any user (authenticated or not) AS PER REQUEST.
    Handles GET requests.
    *** SECURITY WARNING: In a real application, you would likely restrict
        this view to authenticated admin users (e.g., using IsAdminUser). ***
    """

    queryset = ContactMessage.objects.all()
    serializer_class = ContactMessageSerializer
    permission_classes = [
        permissions.AllowAny
    ]  # Allow anyone to list messages (as requested)


class MessageDetailView(generics.RetrieveUpdateAPIView):
    """
    API endpoint that allows retrieving or updating a specific contact message by its ID.
    Accessible by any user (authenticated or not) AS PER REQUEST.
    Handles GET, PUT, PATCH requests.
    *** SECURITY WARNING: In a real application, you would likely restrict
        this view to authenticated admin users (e.g., using IsAdminUser),
        especially the update capability. ***
    """

    queryset = ContactMessage.objects.all()
    serializer_class = ContactMessageSerializer
    permission_classes = [
        permissions.AllowAny
    ]  # Allow anyone to retrieve/update messages (as requested)
    lookup_field = "pk"  # Use the primary key (id) from the URL to find the message


class MarketSummaryView(APIView):
    permission_classes = [permissions.AllowAny]
    """
    API view to fetch basic market data for the NSE All-Share Index using tvdatafeed
    and additional market statistics from NGX API.
    """

    def get(self, request, format=None):
        index_symbol = "ASI"
        exchange = "NSENG"  # Nigerian Exchange Group

        try:
            tv = TvDatafeed()

            logger.info(f"Fetching latest data for {index_symbol} on {exchange}...")
            # Get 2 days of data in a single call
            index_data = tv.get_hist(
                symbol=index_symbol,
                exchange=exchange,
                interval=Interval.in_daily,
                n_bars=2,
            )

            if index_data is None or index_data.empty:
                logger.warning(f"No data returned for {index_symbol} on {exchange}.")
                return Response(
                    {
                        "error": f"Could not fetch data for {index_symbol} on {exchange}."
                    },
                    status=status.HTTP_404_NOT_FOUND,
                )

            # Process the data
            if len(index_data) > 1:
                latest = index_data.iloc[-1]  # Get the last row
                previous = index_data.iloc[-2]  # Get the previous row
                previous_close = previous["close"]
                change = latest["close"] - previous_close
                percent_change = (
                    (change / previous_close) * 100 if previous_close else 0
                )
            else:
                # Only one data point available
                latest = index_data.iloc[-1]
                change = (
                    latest["close"] - latest["open"]
                )  # Change from open if no previous close
                percent_change = (
                    (change / latest["open"]) * 100 if latest["open"] else 0
                )

            # Fetch additional market data from NGX API
            ngx_api_url = "https://doclib.ngxgroup.com/REST/api/mrkstat/mrksnapshot"
            try:
                logger.info(f"Fetching market snapshot from NGX API: {ngx_api_url}")
                import requests

                ngx_response = requests.get(ngx_api_url, timeout=10)
                ngx_response.raise_for_status()  # Raise exception for 4XX/5XX responses
                ngx_data = ngx_response.json()

                # Extract volume and capitalization from NGX data with default values of 0
                volume = ngx_data.get("VOLUME", 0)
                market_cap = ngx_data.get("CAP", 0)

                logger.info(
                    f"Successfully fetched NGX market data: volume={volume}, market_cap={market_cap}"
                )
            except Exception as ngx_error:
                logger.error(
                    f"Error fetching data from NGX API: {ngx_error}", exc_info=True
                )
                # Set default values of 0 if NGX API call fails
                volume = 0
                market_cap = 0

            response_data = {
                "symbol": index_symbol,
                "exchange": exchange,
                "last_update_time": (
                    latest.name.isoformat()
                    if isinstance(latest.name, pd.Timestamp)
                    else str(latest.name)
                ),
                "point_change": round(change, 2),
                "percent_change": round(percent_change, 2),
                "last_price": latest["close"],
                "volume": volume,  # Add volume from NGX API (will be 0 if not available)
                "market_capitalization": market_cap,  # Add market cap from NGX API (will be 0 if not available)
                "market_breadth": [],
                "top_gainers": [],
                "top_losers": [],
            }

            logger.info(f"Successfully fetched combined data: {response_data}")
            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error fetching data: {e}", exc_info=True)
            return Response(
                {"error": f"An error occurred: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
