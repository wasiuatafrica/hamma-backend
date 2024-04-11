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
    from_email = "teamgohamma@gmail.com"
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

class Command(BaseCommand):
    

    def handle(self, *args, **options):
        
        # test_email("nexxyb@gmail.com",'Wasiu','welcome_competition2',"Welcome to Hamma")
        # test_email("nexxyb@gmail.com",'Wasiu','welcome_1b',"Why you should join a Clan!")
        # test_email("nexxyb@gmail.com",'Wasiu','welcome_1c',"Why you should create a Clan!")
        # test_email("nexxyb@gmail.com",'Wasiu','after_signup_36h',"Are We Friends on Social Media?")
        # test_email("nexxyb@gmail.com",'Wasiu','two_days_before_start','BEFORE STEPPING ON HAMMA STAGE!')
        # test_email("nexxyb@gmail.com",'Wasiu','saturday_evening','Wasiu, WHERE DO YOU STAND?')
        # test_email("nexxyb@gmail.com",'Wasiu Ade','four_days_before_end',"Keep Pushing Forward - You're Doing Great!","Wasiu Ade")
        # test_email2("nexxyb@gmail.com",'friday_evening','GUESS WHO MADE TOP TRADER FOR THE WEEK?',"Daniel","PLUTOVERSE")
        # test_email("nexxyb@gmail.com",'Wasiu','mid_competition',"DO THIS IF YOU DON'T WANT TO WIN")
        # test_email("nexxyb@gmail.com",'Wasiu','last_day',"Congratulations - You're a Hamma Trading Competition Champion!")
        # test_email("nexxyb@gmail.com",'Wasiu','two_days_before_end',"Finish Strong in the Hamma Trading Competition!")
        # test_email("nexxyb@gmail.com",'Wasiu','three_days_after_end',"Reflecting on the Hamma Trading Competition Journey")
        
        # test_email("dev.ft9ja@gmail.com",'Joseph','welcome_competition2',"Welcome to Hamma")
        # test_email("dev.ft9ja@gmail.com",'Joseph','welcome_1b',"Why you should join a Clan!")
        # test_email("dev.ft9ja@gmail.com",'Joseph','welcome_1c',"Why you should create a Clan!")
        # test_email("dev.ft9ja@gmail.com",'Joseph','after_signup_36h',"Are We Friends on Social Media?")
        # test_email("dev.ft9ja@gmail.com",'Joseph','two_days_before_start','BEFORE STEPPING ON HAMMA STAGE!')
        # test_email("dev.ft9ja@gmail.com",'Joseph','saturday_evening','Joseph, WHERE DO YOU STAND?')
        # test_email("dev.ft9ja@gmail.com",'Joseph Ade','four_days_before_end',"Keep Pushing Forward - You're Doing Great!",'Joseph Owen',)
        # # test_email("dev.ft9ja@gmail.com",'Joseph','friday_evening','GUESS WHO MADE TOP TRADER FOR THE WEEK?',"Daniel","PLUTOVERSE")
        # test_email("dev.ft9ja@gmail.com",'Joseph','mid_competition',"DO THIS IF YOU DON'T WANT TO WIN")
        # test_email("dev.ft9ja@gmail.com",'Joseph','last_day',"Congratulations - You're a Hamma Trading Competition Champion!")
        # test_email("dev.ft9ja@gmail.com",'Joseph','two_days_before_end',"Finish Strong in the Hamma Trading Competition!")
        # test_email("dev.ft9ja@gmail.com",'Joseph','three_days_after_end',"Reflecting on the Hamma Trading Competition Journey")
        
        
        # test_email("ayo@ft9ja.com",'Ayo','welcome_competition2',"Welcome to Hamma")
        # test_email("ayo@ft9ja.com",'Ayo','welcome_1b',"Why You Should Join a Clan!")
        # test_email("ayo@ft9ja.com",'Ayo','welcome_1c',"Why You Should Create a Clan!")
        # test_email("ayo@ft9ja.com",'Ayo','after_signup_36h',"Are We Friends on Social Media?")
        # test_email("ayo@ft9ja.com",'Ayo','two_days_before_start','BEFORE STEPPING ON HAMMA STAGE!')
        # test_email("ayo@ft9ja.com",'Ayo','saturday_evening','Ayo, WHERE DO YOU STAND?')
        # test_email("ayo@ft9ja.com",'Ayo Test','four_days_before_end',"Keep Pushing Forward - You're Doing Great!",'Ayo Test')
        # test_email2("ayo@ft9ja.com",'friday_evening','GUESS WHO MADE TOP TRADER FOR THE WEEK?',"Daniel","PLUTOVERSE")
        # test_email("ayo@ft9ja.com",'Ayo','mid_competition',"DO THIS IF YOU DON'T WANT TO WIN")
        # test_email("ayo@ft9ja.com",'Ayo','last_day',"Congratulations - You're a Hamma Trading Competition Champion!")
        # test_email("ayo@ft9ja.com",'Ayo','two_days_before_end',"Finish Strong in the Hamma Trading Competition!")
        # test_email("ayo@ft9ja.com",'Ayo','three_days_after_end',"Reflecting on the Hamma Trading Competition Journey")
        
        
        # test_email("teamft9ja@gmail.com",'Ayo','welcome_competition2',"Welcome to Hamma")
        # test_email("teamft9ja@gmail.com",'Ayo','welcome_1b',"Why you should join a Clan!")
        # test_email("teamft9ja@gmail.com",'Ayo','welcome_1c',"Why you should create a Clan!")
        # test_email("teamft9ja@gmail.com",'Ayo','after_signup_36h',"Are We Friends on Social Media?")
        # test_email("teamft9ja@gmail.com",'Ayo','two_days_before_start','BEFORE STEPPING ON HAMMA STAGE!')
        # test_email("teamft9ja@gmail.com",'Ayo','saturday_evening','Ayo, WHERE DO YOU STAND?')
        # test_email("teamft9ja@gmail.com",'Ayo Test','four_days_before_end',"Keep Pushing Forward - You're Doing Great!",'Ayo Test')
        test_email2("teamft9ja@gmail.com",'friday_evening','GUESS WHO MADE TOP TRADER FOR THE WEEK?',"Daniel","PLUTOVERSE")
        # test_email("teamft9ja@gmail.com",'Ayo','mid_competition',"DO THIS IF YOU DON'T WANT TO WIN")
        # test_email("teamft9ja@gmail.com",'Ayo','last_day',"Congratulations - You're a Hamma Trading Competition Champion!")
        # test_email("teamft9ja@gmail.com",'Ayo','two_days_before_end',"Finish Strong in the Hamma Trading Competition!")
        # test_email("teamft9ja@gmail.com",'Ayo','three_days_after_end',"Reflecting on the Hamma Trading Competition Journey")