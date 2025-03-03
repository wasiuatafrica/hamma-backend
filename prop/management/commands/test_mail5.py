from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.core.mail import send_mail
from prop.tasks import send_reminder_email
import waitlist
from waitlist.models import Waitlist

User = get_user_model()


def test_email3(email, firstname):

    context = {"firstname": firstname}
    html_message = render_to_string("prop/ref_program_intro.html", context)
    plain_message = ""
    subject = " Earn & Give – 10% with Our Referral Program!"
    from_email = "Hamma Team <hello@gohamma.com>"
    recipient_list = [email]
    send_mail(
        subject, plain_message, from_email, recipient_list, html_message=html_message
    )


class Command(BaseCommand):

    def handle(self, *args, **options):
        # test_email3("odebunmiwasiu124@gmail.com", "Wasiu")
        # test_email3('edetjoseph05@gmail.com', 'Joseph')
        # test_email3('ayo@gohamma.com', 'Ayo')
        # test_email3("teamgohamma@gmail.com", "Ayo")
        # test_email3('wasiu@atafrica.org', 'Ayo')
        # test_email3("akwasonhumbile@gmail.com", "Daniel")

        # user = User.objects.get(email="nexxyb@gmail.com")
        # task = send_reminder_email(user.id, "GOHAMMAWASIU101", "02-02-2025 10:42")
        # print(task)

        users = User.objects.all().order_by("firstname")
        user_emails = [user.email for user in users]
        waitlist = Waitlist.objects.all()
        for user in waitlist:
            if user.email in user_emails:
                continue
            print(user.email, user.firstname)
            # test_email3(user.email, user.firstname)
