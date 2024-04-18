from rest_framework import serializers
from .models import Waitlist, JoinClick

class WaitlistSerializer(serializers.ModelSerializer):
    class Meta:
        model = Waitlist
        fields = ('id', 'email')
        # read_only_fields = ('created_at', 'updated_at')
        
class JoinClickSerializer(serializers.ModelSerializer):
    class Meta:
        model = JoinClick
        fields = '__all__'