from django.contrib import admin
from . import models

admin.site.register(models.RewardActivities)
admin.site.register(models.Rankings)
admin.site.register(models.ReferralWallet)
admin.site.register(models.ReferralWithdrawalRequest)
admin.site.register(models.BrokageCommission)
admin.site.register(models.CampaignQuarter)
admin.site.register(models.CampaignSummary)
# Register your models here.
