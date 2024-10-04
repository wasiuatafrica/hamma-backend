import os
import boto3
from django.core.management.base import BaseCommand
from django.conf import settings
from django.core.files import File  # Import Django's File class
from supportwithemail.models import SupportAdminProfile  # Ensure this points to your actual model


class Command(BaseCommand):
    help = 'Uploads files to AWS S3 and creates model instances'

    def handle(self, *args, **kwargs):
        data = [
            {
                "name": "George",
                "gender": "male",
                "file_path": "male_profile.jpg"
            },
            {
                "name": "Joy",
                "gender": "female",
                "file_path": "female_profile.jpg"
            }
        ]

        # Initialize the S3 client
        s3 = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME,
        )

        bucket_name = settings.AWS_STORAGE_BUCKET_NAME

        # Loop through the data and process each item
        for item in data:
            file_path = item["file_path"]
            name = item["name"]
            gender = item["gender"]

            # Ensure no duplicate profile is created
            profile_exists = SupportAdminProfile.objects.filter(name=name).exists()
            if profile_exists:
                self.stdout.write(self.style.WARNING(f"Profile for {name} already exists. Skipping."))
                continue

            # Ensure the file exists locally
            if not os.path.isfile(file_path):
                self.stdout.write(self.style.ERROR(f"File '{file_path}' does not exist."))
                continue

            file_name = os.path.basename(file_path)

            try:
                # # Upload the file to S3
                # with open(file_path, 'rb') as file_data:
                #     s3.upload_fileobj(file_data, bucket_name, file_name)
                #     self.stdout.write(self.style.SUCCESS(f"File '{file_name}' uploaded successfully to bucket '{bucket_name}'."))

                # # Generate S3 URL
                # s3_file_url = f"https://{bucket_name}.s3.{settings.AWS_S3_REGION_NAME}.amazonaws.com/{file_name}"

                # Open the image file and wrap it in Django's File class
                with open(file_path, 'rb') as img_file:
                    django_file = File(img_file)  # Wrap in Django's File class
                    
                    # Create a model instance
                    instance = SupportAdminProfile.objects.create(
                        name=name,
                        gender=gender,
                        profile_url=django_file  # Pass the wrapped file object
                    )

                self.stdout.write(self.style.SUCCESS(f"Model instance created with ID {instance.id} for {name}."))

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error processing file '{file_name}': {e}"))
                continue
