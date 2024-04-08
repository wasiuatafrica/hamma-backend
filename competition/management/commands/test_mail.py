import json
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from accounts.tasks import send_welcome_email
from django.template.loader import render_to_string
from django.core.mail import send_mail

User=get_user_model()

def test_email(email,firstname): 
    
    context={
        "firstname":firstname,
    }
    html_message = render_to_string('competition/welcome_competition2.html', context)
    plain_message = ""
    subject = "Welcome to Hamma"
    from_email = "teamgohamma@gmail.com"
    recipient_list = [email]
    send_mail(subject, plain_message, from_email, recipient_list, html_message=html_message)

class Command(BaseCommand):
    

    def handle(self, *args, **options):
        # test_email("nexxyb@gmail.com",'Wasiu')
        # test_email("wasiu@atafrica.org",'Wasiu')
        
        # test_email("dev.ft9ja@gmail.com",'Joseph')
        
        test_email("ayo@ft9ja.com",'Ayo')
        test_email("teamft9ja@gmail.com",'Ayo')