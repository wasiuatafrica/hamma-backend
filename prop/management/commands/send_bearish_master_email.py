import csv
import re
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.template.loader import render_to_string

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

TEMPLATE_NAME = "campaign/all_rounder.html"
SUBJECT = "The ₦200,000 All-Round Challenge is Open"
FROM_EMAIL = "Joy from HammaSwipe <hello@gohamma.com>"


def is_valid_email(email: str) -> bool:
    """Basic validation to weed out throwaway/test domains."""
    if not email or "@" not in email:
        return False

    local_part, domain = email.strip().lower().split("@", 1)
    if not local_part or not domain:
        return False

    if "@test" in email.lower():
        return False

    if re.search(r"@[a-zA-Z]{1,2}\.com$", email):
        return False

    if domain in INVALID_EMAIL_DOMAINS:
        return False

    return True


def send_bearish_master_email(user_email: str, firstname: str) -> None:
    """
    Send the winning streak to a single recipient.

    Args:
        user_email: recipient email address
        firstname: user's first name
    """
    if not is_valid_email(user_email):
        raise ValueError(f"Invalid email detected: {user_email}")

    name = firstname.strip().title() if firstname else "Trader"
    context = {"name": name, "sent_at": datetime.utcnow()}

    html_message = render_to_string(TEMPLATE_NAME, context)
    send_mail(
        SUBJECT,
        "",
        FROM_EMAIL,
        [user_email],
        html_message=html_message,
    )


def load_external_users(csv_filename: str = "users_exter.csv") -> list[tuple[str, str]]:
    """Read external recipients (email, firstname) from CSV."""
    csv_path = Path(settings.BASE_DIR) / csv_filename
    if not csv_path.exists():
        return []

    recipients: list[tuple[str, str]] = []
    with csv_path.open(mode="r", encoding="utf-8", newline="") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            email = (row.get("email") or "").strip()
            if not email:
                continue

            fullname = (row.get("full name") or "").strip()
            firstname = fullname.split()[0] if fullname else ""
            recipients.append((email, firstname))

    return recipients


class Command(BaseCommand):
    help = "Send the Bearish Master campaign email to active users."

    def handle(self, *args, **options):

        # send_bearish_master_email("dev8.ft9ja@gmail.com", "Wasiu")
        # send_bearish_master_email("teamft9ja@gmail.com", "Ayo")

        queryset = (
            User.objects.filter(is_active=True)
            .exclude(email__isnull=True)
            .exclude(email="")
            .order_by("email")
        )

        recipients: dict[str, tuple[str, str]] = {}
        for user in queryset:
            email = (user.email or "").strip()
            firstname = (user.firstname or "").strip() or "Trader"
            if not email:
                continue

            recipients[email.lower()] = (email, firstname)

        external_recipients = load_external_users()
        for email, firstname in external_recipients:
            key = email.lower()
            if key in recipients:
                continue
            recipients[key] = (email, firstname.strip())

        total = len(recipients)
        self.stdout.write(self.style.SUCCESS(f"Total unique users to email: {total}"))

        sent = 0
        for email, firstname in recipients.values():
            if not is_valid_email(email):
                self.stdout.write(
                    self.style.WARNING(f"Skipping invalid email: {email}")
                )
                continue

            try:
                send_bearish_master_email(email, firstname)
            except ValueError as exc:
                self.stdout.write(self.style.WARNING(str(exc)))
                continue

            sent += 1
            self.stdout.write(
                self.style.SUCCESS(
                    f"✓ Sent winning streak to {email} ({firstname.title() or 'Trader'})"
                )
            )

        self.stdout.write(
            self.style.SUCCESS(f"Completed sending winning streak to {sent} user(s).")
        )
