from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta, datetime

from competition.models import JoinClanRequest
from notifications.utils import save_and_send_notification
from competition.managers.utils import sendMail

from django.contrib.auth import get_user_model

User = get_user_model()
class Command (BaseCommand):
    help = 'Set all existing TradeAccount updated field to 1 hour ago'

    def handle (self, *args, **options):
        
        join_requests = JoinClanRequest .objects.filter(approved='pending')
        
        for req in join_requests:
            diff = timezone.now() - req.date_request
            if diff.days > 2:
                req.status = 'rejected'
                req.save()
                save_and_send_notification(req.user.id, "Your clan join request has been rejected")
                mail=sendMail("competition/joinClanRejected.html","Join a Clan (Rejected)",[req.user.email],{"first_name":req.user.firstname.title(), "clan_name":req.clan.clan_name.title()})
        print("check pending join clan requests done for today")