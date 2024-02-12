import json
from django.core.management.base import BaseCommand
from portfolio.models import Stock
from affilate.utils import get_quarter, get_quarter_dates, get_rank_details
from affilate.models import CampaignQuarter, CampaignSummary, RewardActivities, BrokageCommission
from accounts.models import Referral
from django.db.models import Sum
from django.contrib.auth import get_user_model

User=get_user_model()


class Command(BaseCommand):
    help = 'Save all Stock symbols as JSON file'

    def handle(self, *args, **options):
        campaign= CampaignQuarter.objects.filter(status='ongoing').last()
        if campaign:
            first_day, last_day = get_quarter_dates()
            data_list=[]
            users = Referral.objects.all()
            for user in users:
                data_list.append(get_rank_details(user.user, first_day))
                
            sorted_data = sorted(data_list, key=lambda x: x['brokerage_commission'], reverse=True)
            for rank, data in enumerate(sorted_data, start=1):
                user = User.objects.get(id=data['user_id'])
                summary = CampaignSummary.objects.create(
                    campaign=campaign,
                    user=user,
                    earnings=data['brokerage_commission'],
                    referrals=data['active_referees'],
                    rank=rank,
                )
                print(rank)
            campaign.status='closed'
            campaign.save()