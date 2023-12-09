from rest_framework import serializers
from portfolio import models
from accounts import serializers as acc_serializers

class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

class AdminReceiptsViewSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()
    fullname = serializers.SerializerMethodField()
    
    class Meta:
        model = models.Receipts
        fields = ('id', 'user','fullname', 'amount', 'payment_method', 'receipt_status', 
                  'comment', 'created', 'approved_date', 'image_url')
        
    def get_image_url(self, obj):
        if obj.image:
            # print(obj.image.url)
            return obj.image.url
        return None
    
    def get_fullname(self, obj):
        user = obj.user
        if user:
            return f"{user.firstname.title()} {user.lastname.title()}"
        
        
class WithdrawalSerializer(serializers.ModelSerializer):
    fullname = serializers.SerializerMethodField()
    user_id = serializers.SerializerMethodField()
    class Meta:
        model = models.WithdrawalRequest
        fields = (
            'id',
            'fullname',
            'user_id',
            'amount',
            'status',
            'created'
        )
        
    
    def get_fullname(self, obj):
        user = obj.wallet.user
        if user:
            return user.fullname
        
    def get_user_id(self, obj):
        user = obj.wallet.user
        if user:
            return user.id
        
class TradeSerializer(serializers.ModelSerializer):
    fullname = serializers.SerializerMethodField()
    user_id = serializers.SerializerMethodField()
    symbol = serializers.SerializerMethodField()
    
    class Meta:
        model = models.Trade
        fields = (
            'id',
            'symbol',
            'order_type',
            'quantity',
            'price',
            'status',
            'updated',
            'fullname',
            'user_id',
            
        )
        
    def get_fullname(self, obj):
        user = obj.user
        if user:
            return f"{user.firstname.title()} {user.lastname.title()}"
        
    def get_user_id(self,obj):
        return obj.user.id
    
    def get_symbol(self,obj):
        return obj.holding.stock.symbol