import os
from django.core.management.base import BaseCommand
from tradingai.tasks import get_tv_signal_task


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        get_tv_signal_task()
