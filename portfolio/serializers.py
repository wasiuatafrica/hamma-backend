from django.contrib.auth import authenticate, get_user_model
from django.utils.translation import gettext_lazy as _
from rest_framework import exceptions, serializers

UserModel = get_user_model()

from rest_framework import serializers
from .models import DashboardFeed, FeedsCategory, Wallet, Stock, Receipts, PayStackReceipts,Transaction, Alert, Conversation, ButtonClick

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
        fields = (
            'company',
            'symbol',
            'sector',
            'current_price',
            'change',
            'percent_change'
        )
    

class ReceiptsViewSerializer(serializers.ModelSerializer):
    class Meta:
        model = Receipts
        fields = ["image"]
        
class PayStackReceiptsSerializer(serializers.ModelSerializer):
    class Meta:
        model = PayStackReceipts
        fields = "__all__"

class AlertSerializer(serializers.ModelSerializer):
    class Meta:
        model=Alert
        fields= fields = [
            'id', 'stock', 'alert_name', 'description', 
            'alert_type', 'action', 'to_price', 'to_volume', 
            'frequency', 'expire',  'trigerred'
        ]
        
class ConversationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Conversation
        fields = "__all__"

class ButtonClickSerializer(serializers.ModelSerializer):
    class Meta:
        model = ButtonClick
        fields = ['button_name', 'page'] 
        
class DashboardFeedSerializer(serializers.ModelSerializer):
    class Meta:
        model = DashboardFeed
        fields = "__all__"
        
class FeedsCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = FeedsCategory
        fields = ['name']