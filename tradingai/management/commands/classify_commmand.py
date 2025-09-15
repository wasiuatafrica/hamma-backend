import os

from django.core.management.base import BaseCommand

from tradingai.asset_classify import classify
from tradingai.signal_scrape import get_signal_tv


class Command(BaseCommand):
    help = "Uploads files to AWS S3 and creates model instances"

    def handle(self, *args, **kwargs):
        classify()
        # get_signal_tv()
