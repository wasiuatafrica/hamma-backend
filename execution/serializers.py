from rest_framework import serializers
from portfolio.models import Stock
from .models import DemoPosition,DemoPortfolio

# class TradeSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = Trade
#         fields = '__all__'

class DemoPositionSerializer(serializers.ModelSerializer):
    class Meta:
        model = DemoPosition
        fields = '__all__'

class DemoPortfolioCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = DemoPortfolio
        fields = ['account_name', "user","account_type"]
        extra_kwargs ={
            "user":{"read_only":True}
        }

class DemoPortfolioSerializer(serializers.ModelSerializer):
    class Meta:
        model = DemoPortfolio
        fields =  ['account_name', "user","account_type","balance", "id",]
        extra_kwargs ={
            "user":{"read_only":True}
        }
