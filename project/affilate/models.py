from django.db import models
from django.contrib.auth import get_user_model
import auto_prefetch
# Create your models here.

User=get_user_model()


class RewardActivities(auto_prefetch.Model):
    user = auto_prefetch.ForeignKey(User, on_delete=models.CASCADE,related_name='referrer', null=True, blank=True)
    trader = auto_prefetch.ForeignKey(User, on_delete=models.CASCADE,related_name='person_refeered', null=True, blank=True)
    date=models.DateField(auto_now_add=True)
    reward_type=models.CharField(max_length=50, choices=(("Purchased an account", "Purchased an account"), ("Brokage Commission", "Brokage Commission")))
    amount=models.FloatField()
    status=models.CharField(max_length=50, default="unprocessed",choices=(("approved","approved"), ("declined","declined"),("pending","pending")), null=True, blank=True)
    comment=models.CharField(max_length=50,null=True, blank=True)


    def __str__(self):
        return f"{self.trader.firstname} | {self.reward_type}"

    @property
    def username(self):
        return f"{self.trader.firstname} {self.trader.lastname}"
    
    def save(self, *args, **kwargs):
        if not self.status:
            self.status= "unprocessed"
        super(RewardActivities, self).save(*args, **kwargs)

class Rankings(auto_prefetch.Model):
    user = auto_prefetch.ForeignKey(User, on_delete=models.CASCADE,related_name='ranking_user', null=True, blank=True)
    min_brokage_commission=models.FloatField()
    referal_count=models.IntegerField()

