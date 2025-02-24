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
    """Process trial-related notifications"""
    active_trials = Trial.objects.filter(is_active=True)

    for trial in active_trials:
        days_remaining = trial.days_remaining

        # First day notification (if not sent)
        if not trial.first_reminder_sent and days_remaining <= 13:
            NotificationService.send_trial_reminder_notification(
                trial.user, days_remaining
            )
            trial.first_reminder_sent = True
            trial.save()

        # Halfway notification (7 days)
        elif not trial.halfway_reminder_sent and days_remaining <= 7:
            NotificationService.send_trial_reminder_notification(
                trial.user, days_remaining
            )
            trial.halfway_reminder_sent = True
            trial.save()

        # Final reminder (3 days)
        elif not trial.final_reminder_sent and days_remaining <= 3:
            NotificationService.send_trial_reminder_notification(
                trial.user, days_remaining
            )
            trial.final_reminder_sent = True
            trial.save()

        # Trial ended
        elif not trial.trial_ended_notification_sent and days_remaining <= 0:
            NotificationService.send_trial_ended_notification(trial.user)
            trial.trial_ended_notification_sent = True
            trial.is_active = False
            trial.save()


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
