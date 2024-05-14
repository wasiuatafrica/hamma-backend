from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta, datetime

from competition.models import JoinClanRequest
from notifications.utils import save_and_send_notification
from competition.managers.utils import sendMail

from django.contrib.auth import get_user_model

User = get_user_model()
class Command (BaseCommand):
    help = ''

    def handle (self, *args, **options):
        
        join_requests = JoinClanRequest .objects.filter(approved='pending')
        
        for join_request in join_requests:
            account= join_request.user
            join_request.approved = 'approved'
            join_request.save()
            join_request.clan.member.add(account)
            save_and_send_notification(join_request.user.id, f"Your request to join  {join_request.clan.clan_name.title()}  has been approved")
            mail=sendMail("competition/joinClanApproved.html","Join a Clan (Approved)",[join_request.user.email],{"first_name":join_request.user.firstname, "clan_name":join_request.clan.clan_name})
            print("request approved")