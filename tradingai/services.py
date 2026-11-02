# services.py

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, send_mail
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.html import strip_tags

from notifications.utils import save_and_send_notification

from .models import Subscription, SubscriptionNotification, Trial


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


# class NotificationService:
#     @staticmethod
#     def create_notification(user, notification_type, title, message):
#         """Create notification and send email"""
#         notification = SubscriptionNotification.objects.create(
#             user=user, notification_type=notification_type, title=title, message=message
#         )

#         # Send email
#         send_mail(
#             subject=title,
#             message=message,
#             from_email=settings.DEFAULT_FROM_EMAIL,
#             recipient_list=[user.email],
#             fail_silently=True,
#         )

#         try:
#             save_and_send_notification(user_id=user.id, message=message)
#         except Exception as e:
#             print(f"WebSocket notification failed: {str(e)}")

#         return notification

#     @staticmethod
#     def send_trial_started_notification(user):
#         NotificationService.create_notification(
#             user=user,
#             notification_type="trial_started",
#             title="Welcome to AI Trading Assistant!",
#             message="Your 14-day free trial has started. Enjoy AI-powered trading insights!",
#         )

#     @staticmethod
#     def send_trial_reminder_notification(user, days_remaining):
#         NotificationService.create_notification(
#             user=user,
#             notification_type="trial_reminder",
#             title=f"{days_remaining} Days Left in Your Trial",
#             message=f"Your AI Trading Assistant trial ends in {days_remaining} days. "
#             f"Subscribe now to maintain uninterrupted access!",
#         )

#     @staticmethod
#     def send_trial_ended_notification(user):
#         NotificationService.create_notification(
#             user=user,
#             notification_type="trial_ended",
#             title="Your Trial Has Ended",
#             message="Subscribe now to continue accessing AI-powered trading insights!",
#         )

#     @staticmethod
#     def send_payment_successful_notification(user, plan):
#         NotificationService.create_notification(
#             user=user,
#             notification_type="payment_successful",
#             title="Subscription Activated Successfully",
#             message=f"Your {plan.name} subscription has been activated. Enjoy!",
#         )


class NotificationService:
    @staticmethod
    def create_notification(user, notification_type, title, message):
        """Create notification and send email"""
        notification = SubscriptionNotification.objects.create(
            user=user, notification_type=notification_type, title=title, message=message
        )

        # Send email
        send_mail(
            subject=title,
            message=message,
            from_email="Hamma Team <hello@gohamma.com>",
            recipient_list=[user.email],
            fail_silently=True,
        )

        try:
            save_and_send_notification(user_id=user.id, message=message)
        except Exception as e:
            pass

        return notification

    @staticmethod
    def create_notification_with_template(
        user, notification_type, title, message, template_name, context=None
    ):
        """Create notification and send HTML email using template"""
        if context is None:
            context = {}

        # Ensure first_name is in context
        context["first_name"] = user.firstname.title()

        notification = SubscriptionNotification.objects.create(
            user=user, notification_type=notification_type, title=title, message=message
        )

        # Send HTML email
        html_content = render_to_string(f"ai/{template_name}", context)
        text_content = strip_tags(html_content)

        email = EmailMultiAlternatives(
            subject=title,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user.email],
        )
        email.attach_alternative(html_content, "text/html")

        try:
            email.send(fail_silently=True)
            notification.is_email_sent = True
            notification.save(update_fields=["is_email_sent"])
        except Exception as e:
            pass

        try:
            save_and_send_notification(user_id=user.id, message=message)
        except Exception as e:
            pass

        return notification

    @staticmethod
    def send_trial_started_notification(user):
        """Send notification for when the trial first starts using the first day template"""
        return NotificationService.create_notification_with_template(
            user=user,
            notification_type="trial_started",
            title="Take the Guesswork Out of Trading with AI 📊",
            message="Your 14-day free trial has started. Enjoy AI-powered trading insights!",
            template_name="ai_first_day.html",
            context={"first_name": user.firstname.title()},
        )

    @staticmethod
    def send_one_week_reminder_notification(user):
        """Send notification after 1 week of trial"""
        days_remaining = 7  # One week into the trial means 7 days left
        return NotificationService.create_notification_with_template(
            user=user,
            notification_type="trial_reminder",
            title=f"Still Trading Without AI? Here’s What You’re Missing 🚀",
            message=f"Your AI Trading Assistant trial is halfway complete with {days_remaining} days remaining. "
            f"Subscribe now to maintain uninterrupted access!",
            template_name="ai_after_1_week.html",
            context={"first_name": user.firstname.title()},
        )

    @staticmethod
    def send_three_days_reminder_notification(user):
        """Send notification when there are 3 days left in the trial"""
        days_remaining = 3
        return NotificationService.create_notification_with_template(
            user=user,
            notification_type="trial_reminder",
            title="Only 3 Days Left! Don’t Lose Your AI Trading Edge ⏳",
            message=f"Your AI Trading Assistant trial ends in {days_remaining} days. "
            f"Subscribe now to maintain uninterrupted access!",
            template_name="ai_3days_before_end_trial.html",
            context={"first_name": user.firstname.title()},
        )

    @staticmethod
    def send_trial_ended_notification(user):
        """Send notification when trial has ended"""
        return NotificationService.create_notification_with_template(
            user=user,
            notification_type="trial_ended",
            title="Your AI Access Has Expired—Here’s How to Get It Back 🔄",
            message="Subscribe now to continue accessing AI-powered trading insights!",
            template_name="ai_end_of_trial.html",
            context={"first_name": user.firstname.title()},
        )

    @staticmethod
    def send_payment_successful_notification(user, plan):
        NotificationService.create_notification(
            user=user,
            notification_type="payment_successful",
            title="Subscription Activated Successfully",
            message=f"Your {plan.name} subscription has been activated. Enjoy!",
        )
