import json
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from accounts.tasks import send_welcome_email
from django.template.loader import render_to_string
from django.core.mail import send_mail

User=get_user_model()

def test_email(email,firstname,template,subject,fullname=None,top_trader=None, top_clan=None): 
    
    if top_clan and top_trader :
        context={
            "firstname":firstname,
            "top_clan":top_clan,
            "top_trader":top_trader,
        }
    elif fullname:
        context={
            "fullname":fullname,
        }
    else:
        context={
            "firstname":firstname,
        }
    html_message = render_to_string(f'competition/{template}.html', context)
    plain_message = ""
    subject = subject
    # from_email = "teamgohamma@gmail.com"
    from_email = "hello@mail.gohamma.com"
    recipient_list = [email]
    send_mail(subject, plain_message, from_email, recipient_list, html_message=html_message)

def test_email2(email,template,subject,top_trader, top_clan): 
    
   
    context={
            "top_clan":top_clan,
            "top_trader":top_trader,
        }
   
    html_message = render_to_string(f'competition/{template}.html', context)
    plain_message = ""
    subject = subject
    from_email = "teamgohamma@gmail.com"
    recipient_list = [email]
    send_mail(subject, plain_message, from_email, recipient_list, html_message=html_message)

def test_email3(email,firstname,template,subject,): 
    
    
    context={
            "first_name":firstname,
        }
    html_message = render_to_string(f'competition/{template}.html', context)
    plain_message = ""
    subject = subject
    from_email = "Hamma@gohamma.com"
    recipient_list = [email]
    send_mail(subject, plain_message, from_email, recipient_list, html_message=html_message)

class Command(BaseCommand):
    

    def handle(self, *args, **options):
        
        users = User.objects.filter(is_active=True)
        
        for user in users:
            print(user)
            # test_email3(user.email,user.firstname.title(),"extension2" ,'More Time to Win: Hamma Competition Deadline Extended!')
       
        