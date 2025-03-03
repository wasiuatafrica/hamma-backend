from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.core.mail import send_mail
from prop.tasks import send_reminder_email

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

        users = User.objects.all().order_by("firstname")
        for user in users:
            print(user.email, user.firstname)
            test_email3(user.email, user.firstname)
