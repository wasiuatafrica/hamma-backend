from django.db.models.signals import post_save
from django.dispatch import receiver
from . models import SavingsLock
from django_celery_beat.models import PeriodicTask, CrontabSchedule
import json

@receiver(post_save, sender=SavingsLock)
def schedule_lock_payback(sender, created, instance, **kwargs):
    if created:
         crontab_schedule, created = CrontabSchedule.objects.get_or_create(
            minute=instance.end_date.minute,
            hour=instance.end_date.hour,
            # day_of_week=instance.end_date.day,
            day_of_month=instance.end_date.day,
            month_of_year=instance.end_date.month,
        )
         
         task = PeriodicTask.objects.create(
            crontab=crontab_schedule,
            name=f"Payback Schedule  for {instance.user.email}'s {instance.title} lock",
            task='lock.tasks.update_wallet',
            args=json.dumps([instance.id]),
            one_off=True,  
        )