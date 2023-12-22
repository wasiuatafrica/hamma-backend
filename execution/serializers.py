from rest_framework import serializers
from portfolio.models import Stock, Trade

class TradeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Trade
        fields = '__all__'
