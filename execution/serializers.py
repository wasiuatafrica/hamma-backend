from rest_framework import serializers
from portfolio.models import Stock
from .models import DemoPosition,DemoPortfolio, Position, Portfolio


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



class PositionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Position
        fields = '__all__'

class PortfolioCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Portfolio
        fields = ['account_name', "user","account_type"]
        extra_kwargs ={
            "user":{"read_only":True}
        }

class PortfolioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Portfolio
        fields =  ['account_name', "user","account_type","balance", "id",'account_id']
        extra_kwargs ={
            "user":{"read_only":True}
        }
