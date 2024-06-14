
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.core.mail import send_mail
import openpyxl
from competition.models import Competition, CompetitionPortfolio

User=get_user_model()


def test_email3(email,firstname): 
    
    
    context={
            "first_name":firstname
        }
    html_message = render_to_string('competition/update.html', context)
    plain_message = ""
    subject = "Last Chance to Compete and Win Up to N1,000,000  in the Hamma Nigerian Stocks Competition!"
    from_email = "Hamma <hamma@gohamma.com>"
    recipient_list = [email]
    send_mail(subject, plain_message, from_email, recipient_list, html_message=html_message)

class Command(BaseCommand):
    

    def handle(self, *args, **options):
        # test_email3('odebunmiwasiu124@gmail.com', 'Wasiu')
        # test_email3('ayo@gohamma.com', 'Ayo')
        # test_email3('wasiu@atafrica.org', 'Ayo')
        
        portfolios = CompetitionPortfolio.objects.filter(competition__status='current')
        verified = User.objects.filter(is_active=True)
        print('verified', len(verified))
        users_in_competition = [portfolio.user for portfolio in portfolios]
        print('competition',len(users_in_competition))
        
        users_not_in_competition = User.objects.filter(is_active=True).exclude(id__in=[user.id for user in users_in_competition])
        print(len(users_not_in_competition))
        
        for user in users_not_in_competition:
            print(user.email, user.firstname.title())
            test_email3(user.email, user.firstname.title())