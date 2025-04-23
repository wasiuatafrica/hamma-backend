from . import models
from rest_framework import serializers

# contact/serializers.py
from rest_framework import serializers
from .models import ContactMessage


class ContactMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactMessage
        fields = [
            "id",  # Include the ID
            "full_name",
            "email",
            "subject",
            "message",
            "created_at",
            "responded",  # Allow viewing/updating the responded status
        ]
        read_only_fields = [
            "id",  # ID is generated automatically
            "created_at",  # Timestamp is set automatically
        ]

    # Optional: Add specific validation if needed
    # def validate_subject(self, value):
    #     if "spam" in value.lower():
    #         raise serializers.ValidationError("Subject cannot contain 'spam'.")
    #     return value


class SupportMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.SupportMessage
        fields = ["id", "content", "created", "sender", "thread_value"]


class DetailedSupportMessageDisclaimerSerializer(serializers.ModelSerializer):
    rated_message = SupportMessageSerializer(source="message")
    preceding_user_message = serializers.SerializerMethodField()

    class Meta:
        model = models.SupportMessageDisclaimer
        fields = [
            "id",
            "vote",
            "rated_message",
            "feedback",
            "email",
            "name",
            "preceding_user_message",
        ]

    def get_preceding_user_message(self, obj):
        # Get the message that was rated
        rated_message = obj.message
        if rated_message is None or rated_message.thread is None:
            return None

        # Find the most recent user message that was created before the rated message
        preceding_message = (
            models.SupportMessage.objects.filter(
                thread=rated_message.thread,
                sender="user",
                created__lt=rated_message.created,
            )
            .order_by("-created")
            .first()
        )

        if preceding_message:
            return SupportMessageSerializer(preceding_message).data
        return None


class SupportMessageDisclaimerSerializer(serializers.ModelSerializer):

    class Meta:
        model = models.SupportMessageDisclaimer
        fields = ["vote", "message", "email", "name", "feedback"]


class AdminSupportMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.SupportMessage
        fields = [
            "user_id",
            "id",
            "thread_value",
            "sender",
            "content",
            "thread",
            "created",
            "updated",
            "user_name",
            "user_pics",
            "email",
            "name",
        ]


class AdminSupportThreadsSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.SupportThread
        fields = [
            "id",
            "thread_id",
            "email",
            "is_prop",
            "switched_to_admin_support",
            "created",
            "updated",
        ]
