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
    class Meta:
        model = Holding
        fields = '__all__'

class PortfolioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Portfolio
        fields = '__all__'

class ReceiptsViewSerializer(serializers.ModelSerializer):
    class Meta:
        model = Receipts
        fields = ["image"]
        
class PayStackReceiptsSerializer(serializers.ModelSerializer):
    class Meta:
        model = PayStackReceipts
        fields = "__all__"
