import json
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

User = get_user_model()


class Command(BaseCommand):
    help = "Extract all phone numbers from CustomUser model to a JSON file"

    def handle(self, *args, **options):
        # Get all users and extract phone numbers
        users = User.objects.all()
        phone_numbers = [user.phone for user in users if user.phone]
        
        # Filter: numbers starting with 0 (11 digits) or starting with 234
        filtered_phone_numbers = []
        for phone in phone_numbers:
            # Convert to string and strip whitespace
            phone_str = str(phone).strip()
            
            # Check if it's all digits
            if not phone_str.isdigit():
                continue
            
            # Valid patterns:
            # 1. Starts with 0 and is exactly 11 digits
            # 2. Starts with 234 (replace 234 with 0)
            if phone_str.startswith("0") and len(phone_str) == 11:
                filtered_phone_numbers.append(phone_str)
            elif phone_str.startswith("234"):
                # Replace 234 with 0
                normalized_phone = "0" + phone_str[3:]
                filtered_phone_numbers.append(normalized_phone)
        
        # Write to JSON file
        output_file = "phone_numbers.json"
        with open(output_file, "w") as f:
            json.dump(filtered_phone_numbers, f, indent=2)
        
        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully extracted {len(filtered_phone_numbers)} valid phone numbers (out of {len(phone_numbers)} total) to {output_file}"
            )
        )

