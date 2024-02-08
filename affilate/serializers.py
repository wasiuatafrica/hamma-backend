from rest_framework import serializers
from . import models
from accounts.models import Referral


class RewardActivitiesSerializer(serializers.ModelSerializer):
    class Meta:
        model=models.RewardActivities
        fields=[
            'id',
            "user",
            "trader",
            'username',
            "reward_type",
            "created",
            "amount",
            "status",
            "comment"
        ]

class RefereeListSerializer(serializers.ModelSerializer):
    username= serializers.SerializerMethodField()
    class Meta:
        model=Referral
        fields=[
            'username',
            'stage',
            'amount_deposit',
            'commission',
            'brokage_commission',
            'status',
            'created'
        ]
        
    def get_username(self, obj):
        return obj.person_referred.fullname
    
class ReferralWithdrawalRequestSerializer(serializers.ModelSerializer):
    fullname = serializers.SerializerMethodField()
    user_id = serializers.SerializerMethodField()
    type = serializers.SerializerMethodField()
    
    class Meta:
        model = models.ReferralWithdrawalRequest
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
        return "referral"