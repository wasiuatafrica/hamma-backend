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
            "created",
            "amount",
            "status",
            "comment"
        ]

