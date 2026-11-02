from datetime import timedelta

import requests
from celery import shared_task
from celery.app import shared_task
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import EmailMultiAlternatives, send_mail
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.timezone import now, timedelta

from competition.managers.utils import sendMail
from execution.models import DemoPortfolio, Portfolio

from .analyzer import (
    analyze_hamma_portfolio_status,
    analyze_portfolio_status,
    analyze_portfolio_status_after_close,
)
from .utils import get_all_balance_equity_data, get_fixed_balance_equity_data, sendMail

User = get_user_model()


@shared_task
def get_all_balance_equity_data_task():
    get_all_balance_equity_data()


@shared_task
def get_current_prop_data_task():
    get_fixed_balance_equity_data()


@shared_task
def analyze_portfolio_status_task():
    portfolios = DemoPortfolio.objects.filter(
        is_prop=True,
        blown=False,
        inactive_by_inactivity=False,
        activated=True,
        has_hamma__isnull=True,
        # account_id="84549103",
        # account_id="50157814",
    )
    # print(portfolios)
    for portfolio in portfolios:
        if portfolio.account_type_level == "challenge":
            data = analyze_portfolio_status(portfolio)
        elif portfolio.account_type_level == "hamma":
            data = analyze_hamma_portfolio_status(portfolio)



@shared_task
def analyze_portfolio_after_close_task(account_id):
    portfolios = DemoPortfolio.objects.filter(
        is_prop=True,
        blown=False,
        inactive_by_inactivity=False,
        activated=True,
        has_hamma__isnull=True,
        account_id=account_id,
        # account_id="76441051",
    )
    # print(portfolios)
    for portfolio in portfolios:
        if portfolio.account_type_level == "challenge":
            data = analyze_portfolio_status_after_close(portfolio)


@shared_task
def send_3days_pending_account_activation_mail():
    """
    Send email to the user after 3 days account inactivation.
    """
    three_days_ago = now() - timedelta(days=3)

    portfolios = DemoPortfolio.objects.filter(
        is_prop=True,
        activated=False,
        receipt_approved=True,
        issued_at__lt=three_days_ago,  # issued date is less than (older than) 3 days ago
    )

    for acc in portfolios:
        # send reminder mails
        sendMail(
            "prop/Pending_Account_Activation.html",
            "Don’t Miss Out — Activate Your Account Today!",
            [acc.user.email],
            {"first_name": acc.user.firstname},
        )


def send_drawdown_volation_mail(user, email, password, key):
    """
    Send email to the user after drawdown violation.
    """
    # Define the payload
    payload = {"email": email, "password": password, "key": key}

    # Make a POST request to the Node.js server
    try:
        resp = requests.post("http://localhost:3000/", json=payload, timeout=50)
        if resp.status_code == 200:
            # Extract the response if successful
            response_data = resp.json()
            draw_down_image_url = response_data.get("url", "URL not provided")

            # Send email with the screenshot URL
            sendMail(
                "prop/DrawDownVoilation.html",
                "Important: Drawdown Violation Alert",
                [user.email],
                {
                    "first_name": user.firstname,
                    "draw_down_image_url": draw_down_image_url,
                },
            )
        else:
            pass
    except requests.exceptions.RequestException as e:
        pass


@shared_task
def send_reminder_email(user_id, discount_code, expiry):
    """
    Send reminder email to users who haven't purchased a prop account.
    """
    try:
        user = User.objects.get(id=user_id)

        # Check if user has purchased a prop account
        has_prop_account = DemoPortfolio.objects.filter(
            user=user, is_prop=True
        ).exists()

        if not has_prop_account:
            # Prepare email content
            context = {
                "firstname": user.firstname,
                "code": discount_code,
                "expiry": expiry,
            }

            subject = "A Promise Fulfilled – Discount for You! 🎉"

            sendMail("prop/ref_program_discount.html", subject, [user.email], context)
            return f"Reminder email sent to {user.email}"

        return f"User {user.email} already has a prop account, no reminder needed"

    except User.DoesNotExist:
        return f"User with ID {user_id} does not exist"
    except Exception as e:
        return f"Error sending reminder email: {str(e)}"


@shared_task
def referral_intro(email, firstname):

    context = {"firstname": firstname}
    html_message = render_to_string("prop/ref_program_intro.html", context)
    plain_message = ""
    subject = " Earn & Give – 10% with Our Referral Program!"
    from_email = "Hamma Team <hello@gohamma.com>"
    recipient_list = [email]
    send_mail(
        subject, plain_message, from_email, recipient_list, html_message=html_message
    )
