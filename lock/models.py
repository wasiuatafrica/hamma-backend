from django.db import models
from django.contrib.auth import get_user_model
from datetime import datetime,timedelta
from decimal import Decimal
import auto_prefetch

User= get_user_model()
class SavingsLock(auto_prefetch.Model):
    DURATION_CHOICES = [
        (30, '30 days'),
        (60, '60 days'),
        (90, '90 days'),
    ]

    
    user = auto_prefetch.ForeignKey(User, on_delete=models.CASCADE)
    title=models.CharField(max_length=255, blank=True, null=True)
    source=models.CharField(max_length=255, blank=True, null=True, default='wallet')
    status=models.CharField(max_length=255, blank=True, null=True, default='ongoing')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    duration = models.IntegerField()
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2, default=5.0)
    start_date = models.DateTimeField(auto_now_add=True)

    @property
    def end_date(self):
        # Calculate the end date based on the start date and duration
        return self.start_date + timedelta(days=self.duration)
        # return self.start_date + timedelta(hours=self.duration, minutes=3)
    

    @property
    def potential_interest(self):
        # Calculate compound interest with monthly compounding
        principal = Decimal(self.amount)
        rate = Decimal(10) / 100
        durations = {
            30:1,
            60:2,
            90:3
        }
        time_in_months = Decimal(durations[self.duration]) 
        compounding_frequency = Decimal(1/12)

        compound_interest = principal * (1 + rate / compounding_frequency)**(compounding_frequency * time_in_months) - principal

        return round(compound_interest, 2)

    @property
    def total_amount_after_lock(self):
        # Calculate the total amount after the lock period including interest
        return round(self.amount + self.potential_interest,2)

    def __str__(self):
        return f"{self.user.username} - {self.amount} {self.duration} days - {self.status}"
