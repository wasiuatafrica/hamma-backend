import os
from django.core.management.base import BaseCommand
from tradingai.utils import process_recommendation


class Command(BaseCommand):
    help = "Uploads files to AWS S3 and creates model instances"

    def handle(self, *args, **kwargs):
        profile = (2, "low", "conservative", [], "Less than a day", "daily")
        rec = process_recommendation(profile)
        print(rec)
