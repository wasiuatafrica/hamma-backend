from django.shortcuts import render
from rest_framework.permissions import AllowAny
from . import serializers
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import SupportMessageDisclaimer,SupportThread,SupportMessage
from django.shortcuts import get_object_or_404


# socket
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.core.serializers.json import DjangoJSONEncoder
import json

# Create your views here.

class RateBotResponse(APIView):
    serializer_class = serializers.SupportMessageDisclaimerSerializer
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"detail":"Feedback recored, thank you."})
        return Response(serializer.errors, status.HTTP_400_BAD_REQUEST)

class SwitchBackToAIBot(APIView):
    permission_classes = [AllowAny]
    
    def put(self, request, thread):
        thread = get_object_or_404(SupportThread, id=thread)
        
        if not thread.switched_to_admin_support:
            return Response({"detail": "Thread is already in AI bot mode."}, status=status.HTTP_400_BAD_REQUEST)
        
        thread.switched_to_admin_support = False
        thread.save()
        
        welcome_message = self.create_welcome_back_message(thread)
        self.notify_chat_socket(welcome_message)
        
        return Response({"detail":"Chat switched back to ai bot successfully."})
    
    def create_welcome_back_message(self, thread):
        content = (
            "Welcome back to the AI assistant! I'm here to help you with any questions or concerns. "
            "Feel free to ask anything, and I'll do my best to assist you. "
            "If you need human support again, just let me know."
        )
        return SupportMessage.objects.create(
            thread=thread,
            sender="assistant",
            content=content
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