from rest_framework import serializers
from . import models


class RewardActivitiesSerializer(serializers.ModelSerializer):
    class Meta:
        model=models.RewardActivities
        fields=[
            'id',
            "user",
            "trader",
            'username',
            "reward_type",
            "date",
            "amount",
            "status",
            "comment"
        ]

class RankingsSerializer(serializers.ModelSerializer):
    class Meta:
        model=models.Rankings
        fields=[
            "user",
            "min_brokage_commission",
            'referal_count',
        ]