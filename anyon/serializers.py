from rest_framework import serializers
from portfolio import models
from accounts import serializers as acc_serializers
from execution.models import WithdrawalRequest, DemoPosition, Position

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
    type = serializers.SerializerMethodField()
    
    class Meta:
        model = WithdrawalRequest
        fields = (
            'id',
            'fullname',
            'user_id',
            'amount',
            'status',
            'created',
            "flag",
            "type"
        )
        
    
    def get_fullname(self, obj):
        user = obj.wallet.user
        if user:
            return user.fullname
        
    def get_user_id(self, obj):
        user = obj.wallet.user
        if user:
            return user.id
        
    def get_type(self,obj):
        return "main"
        
# class TradeSerializer(serializers.ModelSerializer):
#     fullname = serializers.SerializerMethodField()
#     user_id = serializers.SerializerMethodField()
#     symbol = serializers.SerializerMethodField()
    
#     class Meta:
#         model = models.Trade
#         fields = (
#             'id',
#             'symbol',
#             'order_type',
#             'quantity',
#             'price',
#             'status',
#             'updated',
#             'fullname',
#             'user_id',
            
#         )
        
#     def get_fullname(self, obj):
#         user = obj.user
#         if user:
#             return f"{user.firstname.title()} {user.lastname.title()}"
        
#     def get_user_id(self,obj):
#         return obj.user.id
    
#     def get_symbol(self,obj):
#         return obj.holding.stock.symbol
    
class PositionSerializer(serializers.ModelSerializer):
    fullname = serializers.SerializerMethodField()
    user_id = serializers.SerializerMethodField()
    symbol = serializers.SerializerMethodField()
    
    class Meta:
        model = Position
        fields = (
            'id',
            'symbol',
            'action',
            'quantity',
            'open_price',
            'status',
            'updated',
            'fullname',
            'user_id',
            'order_id',
            'order_type',
            'created'
            
        )
        
    def get_fullname(self, obj):
        user = obj.portfolio.user
        if user:
            return f"{user.firstname.title()} {user.lastname.title()}"
        
    def get_user_id(self,obj):
        return obj.portfolio.user.id
    
    def get_symbol(self,obj):
        return obj.stock.symbol
    
class DemoPositionSerializer(serializers.ModelSerializer):
    fullname = serializers.SerializerMethodField()
    user_id = serializers.SerializerMethodField()
    symbol = serializers.SerializerMethodField()
    type =  serializers.SerializerMethodField()
    
    class Meta:
        model = DemoPosition
        fields = (
            'id',
            'symbol',
            'action',
            'quantity',
            'open_price',
            'status',
            'updated',
            'fullname',
            'user_id',
            'order_id',
            'order_type',
            'created',
            'type'
            
        )
        
    def get_fullname(self, obj):
        user = obj.portfolio.user
        if user:
            return f"{user.firstname.title()} {user.lastname.title()}"
        
    def get_user_id(self,obj):
        return obj.portfolio.user.id
    
    def get_symbol(self,obj):
        return obj.stock.symbol
    
    def get_type(self, obj):
        return "Demo"