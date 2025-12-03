import csv
import json
import os
from django.core.management.base import BaseCommand

from accounts.models import Profile


class Command(BaseCommand):
    help = "Extract all phone numbers from Profile model and CSV file to a JSON file"

    def normalize_phone(self, phone):
        """
        Normalize phone number to format starting with 0 and 11 digits.
        Handles: 0xxx, 234xxx, +234xxx, and 10-digit numbers missing leading 0.
        """
        # Convert to string and strip whitespace
        phone_str = str(phone).strip()

        # Remove all spaces
        phone_str = phone_str.replace(" ", "")

        # Remove + sign if present
        if phone_str.startswith("+"):
            phone_str = phone_str[1:]

        # Check if it's all digits after cleaning
        if not phone_str.isdigit():
            return None

        # Valid patterns:
        # 1. Starts with 0 and is exactly 11 digits
        if phone_str.startswith("0") and len(phone_str) == 11:
            return phone_str
        # 2. Starts with 234 (replace 234 with 0)
        elif phone_str.startswith("234") and len(phone_str) >= 13:
            # Replace 234 with 0
            normalized_phone = "0" + phone_str[3:]
            # Ensure it's 11 digits
            if len(normalized_phone) == 11:
                return normalized_phone
        # 3. 10 digits starting with 8 or 9 (missing leading 0)
        elif len(phone_str) == 10 and phone_str[0] in ["8", "9"]:
            return "0" + phone_str

        return None

    def handle(self, *args, **options):
        filtered_phone_numbers = set()  # Use set to avoid duplicates

        # Get all profiles and extract phone numbers
        profiles = Profile.objects.all()
        profile_phones = [profile.phone for profile in profiles if profile.phone]

        # Normalize phone numbers from Profile model
        for phone in profile_phones:
            normalized = self.normalize_phone(phone)
            if normalized:
                filtered_phone_numbers.add(normalized)

        # Read phone numbers from CSV file
        csv_file = "users_3.csv"
        csv_count = 0
        if os.path.exists(csv_file):
            try:
                with open(csv_file, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        phone = row.get("phone", "").strip()
                        if phone:
                            normalized = self.normalize_phone(phone)
                            if normalized:
                                filtered_phone_numbers.add(normalized)
                                csv_count += 1
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"Error reading CSV file: {e}"))
        else:
            self.stdout.write(
                self.style.WARNING(f"CSV file '{csv_file}' not found, skipping...")
            )

        # Convert set to sorted list for consistent output
        filtered_phone_numbers = sorted(list(filtered_phone_numbers))

        # Write to JSON file
        output_file = "phone_numbers.json"
        with open(output_file, "w") as f:
            json.dump(filtered_phone_numbers, f, indent=2)

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully extracted {len(filtered_phone_numbers)} unique valid phone numbers "
                f"({len(profile_phones)} from profiles, {csv_count} from CSV) to {output_file}"
            )
        )
