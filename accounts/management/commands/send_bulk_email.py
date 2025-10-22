import csv
import json
import random
import re
from datetime import datetime
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.template.loader import render_to_string

from accounts.models import Unsubscribe

User = get_user_model()

INVALID_EMAIL_DOMAINS = {
    "example.com",
    "test.com",
    "invalid.com",
    "fake.com",
    "email.com",
    "mailinator.com",
    "tempmail.com",
    "10minutemail.com",
    "yopmail.com",
    "guerrillamail.com",
    "throwaway.email",
    "trash-mail.com",
}


def send_email_to_user(user_email, firstname, template_name, subject):
    """
    Send email to a single user with the specified template and subject.

    Args:
        user_email: Recipient email address
        firstname: User's first name for personalization
        template_name: Path to the HTML email template
        subject: Email subject line
    """
    today = datetime.now()

    context = {
        "firstname": firstname,
        "date": today.date(),
        "email": user_email,
    }

    html_message = render_to_string(template_name, context)
    plain_message = ""
    recipient_list = [user_email]

    from_email = "Hamma Team <hello@gohamma.com>"

    # Send email
    send_mail(
        subject, plain_message, from_email, recipient_list, html_message=html_message
    )


class Command(BaseCommand):
    help = "Send bulk emails to valid users in the database"

    def handle(self, *args, **options):
        # ==================== CONFIGURATION ====================
        # Edit these settings as needed

        template_name = "general/hamma_swipe_intro.html"  # Path to your email template
        subject = "Hamma Swipe: The Nigerian Stock Prediction App That Pays Out."  # Email subject

        ###
        # send_email_to_user("nexxyb@gmail.com", "Devnexx", template_name, subject)
        # send_email_to_user("teamft9ja@gmail.com", "Ayo", template_name, subject)
        # self.stdout.write(self.style.SUCCESS("Email sent successfully."))

        # ======================================================

        # # List of manually exempted users (if any)
        exempted_users = []

        # # Filter valid users
        accounts = User.objects.filter(is_active=True).order_by("email")

        users = [
            account
            for account in accounts
            if account.email not in exempted_users
            and "@test" not in account.email.lower()  # Exclude test emails
            and not re.search(
                r"@[a-zA-Z]{1,2}\.com$", account.email
            )  # Exclude very short domains
            and account.email.split("@")[-1].lower() not in INVALID_EMAIL_DOMAINS
            and account.email  # Ensure email is not empty
            and account.firstname  # Ensure firstname exists
        ]

        total_users = len(users)
        self.stdout.write(
            self.style.SUCCESS(f"\nTotal valid users to email: {total_users}")
        )

        # Confirm before sending
        self.stdout.write(
            self.style.WARNING(f"\nYou are about to send {len(users)} emails.")
        )
        self.stdout.write(f"Template: {template_name}")
        self.stdout.write(f"Subject: {subject}")

        # Send emails
        sent_count = 0
        failed_count = 0

        for user in users:
            try:
                self.stdout.write(
                    f"Sending to: {user.email} ({user.firstname.title()})"
                )
                send_email_to_user(
                    user.email, user.firstname.title(), template_name, subject
                )
                sent_count += 1
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"Failed to send to {user.email}: {str(e)}")
                )
                failed_count += 1

        # Summary
        self.stdout.write("\n" + "=" * 50)
        self.stdout.write(self.style.SUCCESS(f"✓ Successfully sent: {sent_count}"))
        if failed_count > 0:
            self.stdout.write(self.style.ERROR(f"✗ Failed: {failed_count}"))
        self.stdout.write("=" * 50)
