from django.contrib.auth import authenticate, get_user_model
from django.utils.translation import gettext_lazy as _
from rest_framework import exceptions, serializers

UserModel = get_user_model()

from rest_framework import serializers
from .models import Wallet, Stock, Holding, Portfolio, Receipts, PayStackReceipts,Transaction

class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = '__all__'
        
class WalletSerializer(serializers.ModelSerializer):
    class Meta:
        model = Wallet
        fields = ('balance',)
        
class StockSerializer(serializers.ModelSerializer):
    class Meta:
        model = Stock
        fields = '__all__'
    

class HoldingSerializer(serializers.ModelSerializer):
    stock = serializers.SerializerMethodField()
    
    class Meta:
        model = Holding
        fields = (
            'id',
            'stock',
            'quantity',
            'created',
            'updated',
            'filled',
            'incomplete',
            'shares',
            'avg_cost',
            'ltp',
            'cur_val',
            'pnl',
            'change',
            'percent_change',
            'avg_volume_3_months',
            'volume',
            
        )

    def get_stock(self,obj):
        return obj.stock.symbol
    
class PortfolioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Portfolio
        fields = (
            'portfolio_value',
            'total_invested',
            'profit_loss'
        )

class ReceiptsViewSerializer(serializers.ModelSerializer):
    class Meta:
        model = Receipts
        fields = ["image"]
        
class PayStackReceiptsSerializer(serializers.ModelSerializer):
    class Meta:
        model = PayStackReceipts
        fields = "__all__"
