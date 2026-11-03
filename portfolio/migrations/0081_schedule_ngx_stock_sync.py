"""Schedule the NGX stock sync for weekdays at 17:00 Lagos time (after the close)."""

from django.db import migrations

TASK_NAME = "NGX stock sync"


def create_schedule(apps, schema_editor):
    CrontabSchedule = apps.get_model("django_celery_beat", "CrontabSchedule")
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")

    schedule, _ = CrontabSchedule.objects.get_or_create(
        minute="0",
        hour="17",
        day_of_week="1-5",
        day_of_month="*",
        month_of_year="*",
        timezone="Africa/Lagos",
    )
    PeriodicTask.objects.update_or_create(
        name=TASK_NAME,
        defaults={
            "task": "portfolio.tasks.sync_ngx_stocks",
            "crontab": schedule,
            "interval": None,
            "enabled": True,
        },
    )


def remove_schedule(apps, schema_editor):
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    PeriodicTask.objects.filter(name=TASK_NAME).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("portfolio", "0080_stock_sync_runs_and_changes"),
        ("django_celery_beat", "0019_alter_periodictasks_options"),
    ]

    operations = [
        migrations.RunPython(create_schedule, remove_schedule),
    ]
