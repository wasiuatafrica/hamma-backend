from celery.app import shared_task
from .utils import get_all_balance_equity_data, get_fixed_balance_equity_data
from .analyzer import analyze_portfolio_status
from execution.models import DemoPortfolio, Portfolio
from .utils import sendMail
import requests
from django.utils import timezone
from datetime import timedelta
from django.utils.timezone import now, timedelta


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
        # account_id="33642544"
    )
    print(portfolios)
    for portfolio in portfolios:
        if portfolio.account_type_level == "challenge":
            data = analyze_portfolio_status(portfolio)
            print(data)


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
            print(f"Failed to get screenshot: {resp.status_code} - {resp.text}")
    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
