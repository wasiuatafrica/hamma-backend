# services.py

from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone
from .models import Trial, Subscription, SubscriptionNotification
import shortuuid
from notifications.utils import save_and_send_notification


class SubscriptionService:
    @staticmethod
    def create_trial(user):
        """Create a new trial for user"""
        if not Trial.objects.filter(user=user).exists():
            trial = Trial.objects.create(user=user)
            NotificationService.send_trial_started_notification(user)
            return trial
        return None

    @staticmethod
    def process_subscription_payment(user, plan, payment_reference):
        """Process a new subscription"""
        subscription = Subscription.objects.create(
            user=user,
            plan=plan,
            status="active",
            start_date=timezone.now(),
            payment_reference=payment_reference,
        )
        NotificationService.send_payment_successful_notification(user, plan)
        return subscription

    @staticmethod
    def check_subscription_status(user):
        """Check if user has active subscription or trial"""
        # Check subscription
        active_subscription = Subscription.objects.filter(
            user=user, status="active", end_date__gt=timezone.now()
        ).exists()

        if active_subscription:
            return True, "subscription"

        # Check trial
        try:
            trial = Trial.objects.get(user=user, is_active=True)
            if not trial.has_expired:
                return True, "trial"
            trial.is_active = False
            trial.save()
        except Trial.DoesNotExist:
            pass

        return False, None


class NotificationService:
    @staticmethod
    def create_notification(user, notification_type, title, message):
        """Create notification and send email"""
        notification = SubscriptionNotification.objects.create(
            user=user, notification_type=notification_type, title=title, message=message
        )

        # # Send email
        # send_mail(
        #     subject=title,
        #     message=message,
        #     from_email=settings.DEFAULT_FROM_EMAIL,
        #     recipient_list=[user.email],
        #     fail_silently=True,
        # )

        try:
            save_and_send_notification(user_id=user.id, message=message)
        except Exception as e:
            print(f"WebSocket notification failed: {str(e)}")

        return notification

    @staticmethod
    def send_trial_started_notification(user):
        NotificationService.create_notification(
            user=user,
            notification_type="trial_started",
            title="Welcome to AI Trading Assistant!",
            message="Your 14-day free trial has started. Enjoy AI-powered trading insights!",
        )

    @staticmethod
    def send_trial_reminder_notification(user, days_remaining):
        NotificationService.create_notification(
            user=user,
            notification_type="trial_reminder",
            title=f"{days_remaining} Days Left in Your Trial",
            message=f"Your AI Trading Assistant trial ends in {days_remaining} days. "
            f"Subscribe now to maintain uninterrupted access!",
        )

    @staticmethod
    def send_trial_ended_notification(user):
        NotificationService.create_notification(
            user=user,
            notification_type="trial_ended",
            title="Your Trial Has Ended",
            message="Subscribe now to continue accessing AI-powered trading insights!",
        )

    @staticmethod
    def send_payment_successful_notification(user, plan):
        NotificationService.create_notification(
            user=user,
            notification_type="payment_successful",
            title="Subscription Activated Successfully",
            message=f"Your {plan.name} subscription has been activated. Enjoy!",
        )
