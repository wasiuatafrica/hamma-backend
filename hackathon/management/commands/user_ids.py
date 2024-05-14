import os
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from leaderboard.models import Competition, CompetitionSummary, CompetionAccount, TopTraderPayout
from leaderboard.views import rank_clans
class Command(BaseCommand):
    help = 'Save a list of user IDs to a text file'

    # def add_arguments(self, parser):
    #     parser.add_argument('output_file', type=str, help='Output file path')

    def handle(self, *args, **options):
        # output_file = options['output_file']
        
        # user_ids = get_user_model().objects.values_list('email', flat=True)
        # print(type(user_ids))
        
        # with open(output_file, 'w') as file:
        #     for user_id in user_ids:
        #         file.write(str(user_id) + '\n')

        # self.stdout.write(self.style.SUCCESS('User IDs saved to %s' % output_file))
        competition = Competition.objects.get(title="Does it work?")
        # account = CompetionAccount.objects.get(user_account__acc__number=23163360)
        # accounts = CompetitionSummary.objects.filter(competition=competition)
        accounts = TopTraderPayout.objects.filter(competition=competition)
        for summary in accounts:
            print(f"{summary.useracc.user} - {summary.position}")
