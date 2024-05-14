from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta, datetime
from api.models import TradeAccount, UserAccounts, Violations
from leaderboard.models import TopTraderPayout, CompetitionSummary, ClanCompetitionSummary, Competition, Clan

from django.contrib.auth import get_user_model

User = get_user_model()
class Command (BaseCommand):
    help = 'Set all existing TradeAccount updated field to 1 hour ago'

    def handle (self, *args, **options):
        competition=Competition.objects.get(title='Test Competition !')
        user=User.objects.get(email='owenyakubu533@gmail.com')
        # clan=Clan.objects.get(id=16)
        acc = UserAccounts.objects.get(user=user,acc__number=23163360)
        # summ= CompetitionSummary.objects.create(user=user,competition=competition, user_account=acc,profit=24,position=1,clan=clan)
        # summ=ClanCompetitionSummary.objects.create(competition=competition,clan=clan,profit=34, position=1)
        top= TopTraderPayout.objects.create(competition=competition, profit=87,position=5,amount=str(75000),useracc=acc, status='declined')
        print(top.amount)