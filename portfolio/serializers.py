from django.contrib.auth import authenticate, get_user_model
from django.utils.translation import gettext_lazy as _
from rest_framework import exceptions, serializers
from django.db.models import Count, Q

UserModel = get_user_model()

from rest_framework import serializers
from .models import DashboardFeed, FeedsCategory, Wallet, Stock, Receipts, PayStackReceipts,Transaction, Alert, Conversation, ButtonClick,DashboardFeed, FeedReaction

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

    def to_representation(self, instance):
        # Get aggregated counts for each reaction type
        reaction_counts = instance.reactions.aggregate(
            num_agree=Count('id', filter=Q(agree=True)),
            num_disagree=Count('id', filter=Q(disagree=True)),
            num_like=Count('id', filter=Q(like=True)),
            num_trading=Count('id', filter=Q(trading=True)),
            num_monitoring=Count('id', filter=Q(monitoring=True)),
        )
        # Update serializer data with aggregated counts
        ret = super().to_representation(instance)
        ret.update(reaction_counts)
        return ret

        
class FeedsCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = FeedsCategory
        fields = ['name']