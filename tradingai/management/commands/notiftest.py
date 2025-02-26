from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

User = get_user_model()


class Command(BaseCommand):
    help = "Test notification service by sending test emails to a specific user"

    def handle(self, *args, **options):
        # identifier = "nexxyb@gmail.com"
        identifier = "teamgohamma@gmail.com"
        identifier_type = "email"
        notification_type = "all"
        dry_run = False

        # Find the user
        try:
            if identifier_type == "username":
                user = User.objects.get(username=identifier)
            elif identifier_type == "email":
                user = User.objects.get(email=identifier)
            elif identifier_type == "id":
                user = User.objects.get(id=int(identifier))
        except User.DoesNotExist:
            raise CommandError(
                f"User with {identifier_type}={identifier} does not exist"
            )

        self.stdout.write(self.style.SUCCESS(f"Found user: ({user.email})"))

        from tradingai.services import (
            NotificationService,
        )  # Import here to avoid circular imports

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN: No emails will be sent"))

        # Mock subscription plan for testing payment notification
        class MockPlan:
            def __init__(self):
                self.name = "Premium Test Plan"

        mock_plan = MockPlan()

        # Test notifications based on type
        if notification_type in ("all", "trial_start"):
            self._test_notification(
                "Trial Started",
                lambda: NotificationService.send_trial_started_notification(user),
                dry_run,
            )

        if notification_type in ("all", "one_week"):
            self._test_notification(
                "One Week Reminder",
                lambda: NotificationService.send_one_week_reminder_notification(user),
                dry_run,
            )

        if notification_type in ("all", "three_days"):
            self._test_notification(
                "Three Days Reminder",
                lambda: NotificationService.send_three_days_reminder_notification(user),
                dry_run,
            )

        if notification_type in ("all", "trial_end"):
            self._test_notification(
                "Trial Ended",
                lambda: NotificationService.send_trial_ended_notification(user),
                dry_run,
            )

        # if notification_type in ("all", "payment"):
        #     self._test_notification(
        #         "Payment Successful",
        #         lambda: NotificationService.send_payment_successful_notification(
        #             user, mock_plan
        #         ),
        #         dry_run,
        #     )

    def _test_notification(self, name, notification_func, dry_run):
        """Helper method to test a notification with appropriate output"""
        self.stdout.write(f"Testing {name} notification...")

        if dry_run:
            self.stdout.write(
                self.style.WARNING(f"  DRY RUN: Would send {name} notification")
            )
            return

        try:
            result = notification_func()
            self.stdout.write(
                self.style.SUCCESS(f"  ✓ {name} notification sent successfully")
            )
            self.stdout.write(
                f'    - Title: {result.title if hasattr(result, "title") else "N/A"}'
            )
            self.stdout.write(
                f'    - Email sent: {result.is_email_sent if hasattr(result, "is_email_sent") else "N/A"}'
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"  ✗ Failed to send {name} notification: {str(e)}")
            )
