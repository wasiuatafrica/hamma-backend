from rest_framework import serializers
from portfolio.models import Stock, Trade
from .models import DemoPosition

class TradeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Trade
        fields = '__all__'

class DemoPositionSerializer(serializers.ModelSerializer):
    class Meta:
        model = DemoPosition
        fields = '__all__'
