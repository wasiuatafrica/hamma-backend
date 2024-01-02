from django.db.models.signals import post_save
from django.dispatch import receiver
from . models import Alert
from .tasks import create_alert_schedule

@receiver(post_save, sender=Alert)
def schedule_alert(sender, created, instance, **kwargs):
    if created:
        create_alert_schedule.delay(instance.id)