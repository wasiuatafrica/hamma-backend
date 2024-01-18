from django.db import models
from django.contrib.auth import get_user_model
import auto_prefetch
from portfolio.models import Trade

class MasterWallet(auto_prefetch.Model):
    commission = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    created =models.DateTimeField(auto_now_add=True, null=True, blank=True)
    trade = auto_prefetch.ForeignKey(Trade, on_delete=models.CASCADE,related_name='master_wallet', null=True, blank=True)