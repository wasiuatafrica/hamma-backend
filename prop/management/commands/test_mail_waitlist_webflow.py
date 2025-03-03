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
        user_emails = set(
            [user.email for user in users]
        )  # Using set for faster lookups

        # Load emails from CSV file
        df = pd.read_csv("webflow_waitlist.csv")
        scraped_emails = df.iloc[:, 0].tolist()  # Get emails from first column

        # Remove duplicates from scraped emails
        unique_scraped_emails = set(scraped_emails)

        # Filter out emails that are already in the database
        new_emails = unique_scraped_emails - user_emails

        # Send emails to new recipients
        for email in new_emails:
            print(f"Sending to new email: {email}")
            test_email3(email, "Trader")  # Using "Trader" as default firstname

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully sent emails to {len(new_emails)} new recipients"
            )
        )
