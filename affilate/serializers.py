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