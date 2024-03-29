from rest_framework import serializers
from .models import Waitlist

class WaitlistSerializer(serializers.ModelSerializer):
    class Meta:
        model = Waitlist
        fields = ('id', 'email')
        # read_only_fields = ('created_at', 'updated_at')