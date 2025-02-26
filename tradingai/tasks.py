from celery import shared_task
from celery.app import shared_task
from django.utils import timezone

from .asset_classify import classify
from .models import Subscription, Trial
from .services import NotificationService
from .signal_scrape import get_signal_tv


@shared_task
def classify_asset_task():
    classify()


@shared_task
def get_tv_signal_task():
    get_signal_tv()


@shared_task
def process_trial_notifications():
    """
    Process trial-related notifications based on trial stage.

    This task sends email notifications at key points during a user's trial:
    - First day (welcome)
    - After 7 days (halfway point)
    - 3 days before expiration
    - When trial ends

    Each notification uses a specific HTML email template.
    """
    active_trials = Trial.objects.filter(is_active=True)
    now = timezone.now()

    for trial in active_trials:
        user = trial.user
        days_elapsed = (now - trial.start_date).days
        days_remaining = trial.days_remaining
        trial_duration = (trial.end_date - trial.start_date).days
        halfway_point = trial_duration // 2

        # First day notification (welcome email)
        if not trial.first_reminder_sent and days_elapsed == 0:
            NotificationService.send_trial_started_notification(user)
            trial.first_reminder_sent = True
            trial.save(update_fields=["first_reminder_sent"])

        # Halfway notification (typically around 7 days for a 14-day trial)
        elif not trial.halfway_reminder_sent and days_elapsed == halfway_point:
            NotificationService.send_one_week_reminder_notification(user)
            trial.halfway_reminder_sent = True
            trial.save(update_fields=["halfway_reminder_sent"])

        # Three days before end notification
        elif not trial.final_reminder_sent and days_remaining == 3:
            NotificationService.send_three_days_reminder_notification(user)
            trial.final_reminder_sent = True
            trial.save(update_fields=["final_reminder_sent"])

        # Trial ended notification
        elif not trial.trial_ended_notification_sent and days_remaining <= 0:
            NotificationService.send_trial_ended_notification(user)
            trial.trial_ended_notification_sent = True
            trial.is_active = False
            trial.save(update_fields=["trial_ended_notification_sent", "is_active"])

    # Also check for trials that have expired but haven't been marked as inactive
    expired_trials = Trial.objects.filter(
        is_active=True, end_date__lt=now, trial_ended_notification_sent=False
    )

    for trial in expired_trials:
        NotificationService.send_trial_ended_notification(trial.user)
        trial.trial_ended_notification_sent = True
        trial.is_active = False
        trial.save(update_fields=["trial_ended_notification_sent", "is_active"])


@shared_task
def process_subscription_status():
    """Update subscription statuses"""
    now = timezone.now()

    # Update expired subscriptions
    expired_subs = Subscription.objects.filter(status="active", end_date__lte=now)

    for sub in expired_subs:
        sub.status = "expired"
        sub.save()
        NotificationService.create_notification(
            user=sub.user,
            notification_type="subscription_expired",
            title="Subscription Expired",
            message="Your AI Trading Assistant subscription has expired. Renew now to continue!",
        )
