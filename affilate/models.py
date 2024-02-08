from email.policy import default
from django.db import models
from django.contrib.auth import get_user_model
import auto_prefetch
from datetime import datetime
from portfolio.models import Trade
# Create your models here.

User=get_user_model()


class RewardActivities(auto_prefetch.Model):
    user = auto_prefetch.ForeignKey(User, on_delete=models.CASCADE,related_name='reward_activities', null=True, blank=True)
    trader = auto_prefetch.ForeignKey(User, on_delete=models.CASCADE,related_name='person_refeered', null=True, blank=True)
    created=models.DateTimeField(auto_now_add=True)
    reward_type=models.CharField(max_length=50)
    amount=models.FloatField()
    status=models.CharField(max_length=50, default="unprocessed", null=True, blank=True)
    comment=models.CharField(max_length=50,null=True, blank=True)
    flag=models.BooleanField(default=False, null=True, blank=True)


    def __str__(self):
        return f"{self.trader.firstname} | {self.reward_type}"

    @property
    def username(self): 
        return f"{self.trader.firstname} {self.trader.lastname}"
    
        
        
class Rankings(auto_prefetch.Model):
    user = auto_prefetch.ForeignKey(User, on_delete=models.CASCADE,related_name='ranking_user', null=True, blank=True)
    min_brokage_commission=models.FloatField()
    referal_count=models.IntegerField()

class ReferralWallet(auto_prefetch.Model):
    user = auto_prefetch.ForeignKey(User, on_delete=models.CASCADE,related_name='referral_wallet', null=True, blank=True)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    created =models.DateTimeField(auto_now_add=True, null=True, blank=True)
    
class BrokageCommission(auto_prefetch.Model):
    user = auto_prefetch.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    person_refferred = auto_prefetch.ForeignKey(User, on_delete=models.CASCADE,related_name='brokage_commsissions', null=True, blank=True)
    commission = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    created =models.DateTimeField(auto_now_add=True, null=True, blank=True)
    trade = auto_prefetch.ForeignKey(Trade, on_delete=models.CASCADE,related_name='brokage_commsissions', null=True, blank=True)
    
    
class CampaignQuarter(auto_prefetch.Model):
    title = models.CharField(max_length=100)
    first_prize = models.CharField(max_length=30)
    second_prize = models.CharField(max_length=30)
    third_prize = models.CharField(max_length=30)
    created =models.DateTimeField(auto_now_add=True, null=True, blank=True)

class ReferralWithdrawalRequest(auto_prefetch.Model):
    wallet=auto_prefetch.ForeignKey(ReferralWallet, on_delete=models.CASCADE)
    amount = models.DecimalField(null=True, blank=True,max_digits=10, decimal_places=2)
    created = models.DateTimeField(auto_now_add=True,null=True, blank=True)
    updated = models.DateTimeField(auto_now=True)
    status= models.CharField(max_length=20, default='Unprocessed', blank=True,null=True)
    flag=models.BooleanField(default=False, null=True, blank=True)
    