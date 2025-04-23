import json

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.core.serializers.json import DjangoJSONEncoder
from django.shortcuts import get_object_or_404, render
from rest_framework import generics, permissions, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from . import serializers
from .models import (
    ContactMessage,
    SupportMessage,
    SupportMessageDisclaimer,
    SupportThread,
)
from .serializers import ContactMessageSerializer

# Create your views here.


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


# --- View for Creating a Message ---
class MessageCreateView(generics.CreateAPIView):
    """
    API endpoint that allows users to submit a new contact message.
    Accessible by any user (authenticated or not).
    Handles POST requests.
    """

    queryset = (
        ContactMessage.objects.all()
    )  # Required for CreateAPIView, even if not directly used for listing
    serializer_class = ContactMessageSerializer
    permission_classes = [permissions.AllowAny]  # Allow anyone to submit a message


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
