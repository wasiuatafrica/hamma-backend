import os
from django.core.management.base import BaseCommand
from tradingai.asset_classify import classify


class Command(BaseCommand):
    help = "Uploads files to AWS S3 and creates model instances"

    def handle(self, *args, **kwargs):
        classify()
