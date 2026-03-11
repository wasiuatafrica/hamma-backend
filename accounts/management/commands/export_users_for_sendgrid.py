import csv
import re

from django.core.management.base import BaseCommand

from accounts.models import CustomUser


class Command(BaseCommand):
    help = "Extract emails and first names from CustomUser model and export to CSV format for SendGrid"

    def _is_test_or_temporary_email(self, email):
        """
        Check if an email is a test or temporary email address.
        Returns True if the email should be filtered out.
        """
        if not email:
            return True

        email_lower = email.lower().strip()

        # Common temporary/test email domains
        test_domains = [
            "example.com",
            "example.org",
            "test.com",
            "test.org",
            "mailinator.com",
            "10minutemail.com",
            "guerrillamail.com",
            "tempmail.com",
            "temp-mail.org",
            "throwaway.email",
            "fakemail.com",
            "dummy.com",
            "yopmail.com",
            "getnada.com",
            "mohmal.com",
            "dispostable.com",
            "maildrop.cc",
            "tempail.com",
            "mintemail.com",
            "sharklasers.com",
        ]

        # Check domain
        domain = email_lower.split("@")[-1] if "@" in email_lower else ""
        if domain in test_domains:
            return True

        # Check for test/temp patterns in local part (before @)
        local_part = email_lower.split("@")[0] if "@" in email_lower else email_lower
        test_patterns = [
            r"^test",
            r"test$",
            r"^temp",
            r"temp$",
            r"^temporary",
            r"temporary$",
            r"^fake",
            r"fake$",
            r"^dummy",
            r"dummy$",
            r"^no-reply",
            r"^noreply",
            r"^donotreply",
            r"^do-not-reply",
        ]

        for pattern in test_patterns:
            if re.search(pattern, local_part):
                return True

        return False

    def handle(self, *args, **options):
        output_file = "hamma_users_for_sendgrid.csv"

        # Build queryset
        users = CustomUser.objects.all()

        # Filter out users without email or firstname
        users = users.exclude(email__isnull=True).exclude(email__exact="")
        users = users.exclude(firstname__isnull=True).exclude(firstname__exact="")

        # Filter out temporary and test emails
        # We'll filter these during iteration since we need to check the email content
        # This is more efficient than complex Q objects for pattern matching

        total_users = users.count()
        self.stdout.write(self.style.SUCCESS(f"\nTotal users to export: {total_users}"))

        # Write to CSV
        with open(output_file, "w", newline="", encoding="utf-8") as csvfile:
            # SendGrid typically expects: email, first_name (or firstname)
            fieldnames = ["email", "first_name"]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            writer.writeheader()

            exported_count = 0
            skipped_count = 0

            for user in users:
                try:
                    # Clean and validate data
                    email = user.email.strip().lower() if user.email else None
                    firstname = user.firstname.strip() if user.firstname else None

                    # Skip test/temporary emails
                    if self._is_test_or_temporary_email(email):
                        skipped_count += 1
                        continue

                    if email and firstname:
                        writer.writerow(
                            {
                                "email": email,
                                "first_name": firstname,
                            }
                        )
                        exported_count += 1
                    else:
                        skipped_count += 1
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f"Error processing user {user.id}: {str(e)}")
                    )
                    skipped_count += 1

        # Summary
        self.stdout.write("\n" + "=" * 50)
        self.stdout.write(
            self.style.SUCCESS(
                f"✓ Successfully exported {exported_count} users to {output_file}"
            )
        )
        if skipped_count > 0:
            self.stdout.write(
                self.style.WARNING(f"⚠ Skipped {skipped_count} users (missing data)")
            )
        self.stdout.write("=" * 50)
        self.stdout.write(
            self.style.SUCCESS(f"\nCSV file ready for SendGrid upload: {output_file}")
        )
