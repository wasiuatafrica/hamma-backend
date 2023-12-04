from rest_framework import serializers
from portfolio import models
from accounts import serializers as acc_serializers

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