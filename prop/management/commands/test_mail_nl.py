from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.core.mail import send_mail
from prop.tasks import send_reminder_email
import pandas as pd

User = get_user_model()


def test_email3(email, firstname):
    context = {"firstname": firstname}
    html_message = render_to_string("prop/ref_program_intro.html", context)
    plain_message = ""
    subject = "Earn & Give – 10% with Our Referral Program!"
    from_email = "Hamma Team <hello@gohamma.com>"
    recipient_list = [email]
    send_mail(
        subject, plain_message, from_email, recipient_list, html_message=html_message
    )


class Command(BaseCommand):
    def handle(self, *args, **options):
        # Get existing user emails from database
        users = User.objects.all().order_by("firstname")
        user_emails = [user.email.lower() for user in users]

        # Load emails from Excel file
        df = pd.read_excel("scraped_emails_edited.xlsx")
        scraped_emails = df.iloc[:, 0].tolist()  # Get emails from first column

        # Filter out emails that are already in the database
        new_emails = [
            email.lower() for email in scraped_emails if email not in user_emails
        ]

        # Send emails to new recipients
        for email in new_emails:
            print(f"Sending to new email: {email}")
            test_email3(email, "Trader")  # Using "Trader" as default firstname

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully sent emails to {len(new_emails)} new recipients"
            )
        )
