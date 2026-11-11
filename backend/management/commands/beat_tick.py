"""Run due django_celery_beat tasks once, then exit.

Replaces an always-on `celery worker -B` on Railway: a cron service runs this
every 5 minutes (*/5 * * * *). It reads the same PeriodicTask rows beat uses,
so interval, crontab (with their own timezone, e.g. Africa/Lagos) and clocked
one-off tasks created at runtime all keep working, at 5-minute resolution.
Task bodies run in this process (.apply()), so no broker or worker is needed.
"""

import json
import logging
import time
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import close_old_connections
from django.utils import timezone
from django_celery_beat.models import PeriodicTask

from backend.celery import app

log = logging.getLogger("beat_tick")

# Cron start jitter. Without slack, a 5-minute task seen 4m58s after its last
# run would wait for the next tick and drift to every 10 minutes.
SLACK = timedelta(seconds=60)


def is_due(pt, now):
    if pt.start_time and now < pt.start_time:
        return False
    if pt.expires and now >= pt.expires:
        return False
    last = pt.last_run_at
    if pt.clocked_id:
        return pt.clocked.clocked_time <= now + SLACK
    if pt.interval_id:
        return last is None or now - last >= pt.interval.schedule.run_every - SLACK
    if pt.crontab_id:
        if last is None:
            # First sight: don't replay history, schedule from now on.
            pt.last_run_at = now
            pt.save(update_fields=["last_run_at"])
            return False
        # No slack here: running a cron early would record last_run_at before
        # its slot, and the next tick would run it again. Railway starts cron
        # containers at or after the */5 mark, so on-the-mark slots run on time
        # and others (e.g. 08:10) run at the next tick.
        return pt.crontab.schedule.remaining_estimate(last) <= timedelta(0)
    return False  # solar schedules are not used


class Command(BaseCommand):
    help = "Run due django_celery_beat periodic tasks once, then exit (cron)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true", help="List due tasks without running them."
        )

    def handle(self, *args, dry_run=False, **opts):
        app.loader.import_default_modules()  # register every @shared_task
        now = timezone.now()
        tasks = PeriodicTask.objects.filter(enabled=True).select_related(
            "interval", "crontab", "clocked"
        )
        # Frequent interval tasks first, slower crons last, so a long cron
        # can't delay order processing.
        due = sorted(
            (t for t in tasks if is_due(t, now)),
            key=lambda t: (t.interval_id is None, t.name),
        )
        self.stdout.write(f"tick {now:%Y-%m-%d %H:%M:%S}Z: {len(due)} due")
        for pt in due:
            if dry_run:
                self.stdout.write(f"  would run {pt.name} ({pt.task})")
                continue
            task = app.tasks.get(pt.task)
            started = time.monotonic()
            if task is None:
                log.error("task %s: %s is not registered", pt.name, pt.task)
            else:
                try:
                    result = task.apply(
                        args=json.loads(pt.args or "[]"),
                        kwargs=json.loads(pt.kwargs or "{}"),
                    )
                    if result.failed():
                        log.error("task %s failed: %r", pt.name, result.result)
                except Exception:
                    log.exception("task %s failed", pt.name)
            pt.last_run_at = now
            pt.total_run_count += 1
            fields = ["last_run_at", "total_run_count"]
            if pt.one_off or pt.clocked_id:
                pt.enabled = False
                fields.append("enabled")
            pt.save(update_fields=fields)
            self.stdout.write(f"  {pt.name}: {time.monotonic() - started:.1f}s")
            close_old_connections()
