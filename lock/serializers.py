from rest_framework import serializers
from .models import SavingsLock, Saving

class SavingsLockSerializer(serializers.ModelSerializer):
    class Meta:
        model = SavingsLock
        fields = ['id','title','source', 'status', 'amount', 'duration', 'interest_rate', 'start_date',
                  'end_date', 'potential_interest', 'total_amount_after_lock',
                  ]

class SavingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Saving
        fields = ['id','title','source', 'status', 'amount', 'interest_rate', 'start_date',
                  'duration', 'potential_interest', 'total_amount_after_close',
                  ]
