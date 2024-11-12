import json

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django_celery_beat.models import PeriodicTask, CrontabSchedule

from .models import Competition, JoinClanRequest
from .tasks import (
    create_competition,
    setup_competition_emails,
    auto_approve_join_clan_requests,
)


@receiver(post_save, sender=Competition)
def notify_all_users(instance, created, **kwargs):

    if instance.status == "current":
        start_date = instance.start_date

        if start_date > timezone.now():

            start_task_name = f"Competition Start Date Task for {instance.title}"
            start_task_args = [instance.id]

            start_schedule, created1 = CrontabSchedule.objects.get_or_create(
                minute=start_date.minute,
                hour=start_date.hour,
                day_of_month=start_date.day,
                month_of_year=start_date.month,
            )

            try:
                start_task = PeriodicTask.objects.get(name=start_task_name)
                start_task.crontab = start_schedule
                start_task.save()
            except PeriodicTask.DoesNotExist:
                start_task = PeriodicTask.objects.create(
                    name=start_task_name,
                    task="competition.tasks.start_competition",
                    args=json.dumps(start_task_args),
                    one_off=True,
                    crontab=start_schedule,
                )

            create_competition.delay(instance.id, instance.start_date)

        if instance.end_date:
            end_date = instance.end_date
            end_task_name = f"End Date Task for {instance.title}"
            end_task_args = [instance.id]

            end_schedule, created3 = CrontabSchedule.objects.get_or_create(
                minute=end_date.minute,
                hour=end_date.hour,
                day_of_month=end_date.day,
                month_of_year=end_date.month,
            )

            try:
                end_task = PeriodicTask.objects.get(name=end_task_name)
                end_task.crontab = end_schedule
                end_task.save()
            except PeriodicTask.DoesNotExist:
                end_task = PeriodicTask.objects.create(
                    name=end_task_name,
                    task="competition.tasks.end_competition",
                    args=json.dumps(end_task_args),
                    one_off=True,
                    crontab=end_schedule,
                )
    if created:
        setup_competition_emails.delay(instance.id)


@receiver(post_save, sender=JoinClanRequest)
def auto_accept(instance, created, **kwargs):
    if created:
        auto_approve_join_clan_requests.delay(instance.id)
