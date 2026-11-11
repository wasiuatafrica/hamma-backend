from asgiref.sync import sync_to_async
from django.db import close_old_connections


def _run(fn, *args):
    close_old_connections()
    try:
        return fn(*args)
    finally:
        close_old_connections()


def run_in_thread(fn, *args):
    """Run blocking work (e.g. a Celery task body) from an async consumer.

    thread_sensitive=False gives each call its own pool thread, so one slow
    OpenAI call doesn't queue every other websocket user behind it. Pool size
    is capped by the ASGI_THREADS env var.
    """
    return sync_to_async(_run, thread_sensitive=False)(fn, *args)


_background = set()


def dispatch(task, *args):
    """Start a Celery task without waiting for it, from an async consumer.

    With CELERY_EAGER (Railway) the task body runs in a pool thread in this
    process; otherwise it goes to the broker as before. Fire-and-forget on
    purpose: the task replies through the channel layer, and a consumer only
    handles those replies once receive() has returned.
    """
    from django.conf import settings

    if not settings.CELERY_TASK_ALWAYS_EAGER:
        task.delay(*args)
        return
    import asyncio

    # Bind the task here, on the event-loop thread. Celery binds tasks lazily on
    # first use and that step isn't thread-safe: two pool threads hitting an
    # unbound task at once fail with "'NoneType' object has no attribute 'push'".
    task.app
    job = asyncio.ensure_future(run_in_thread(task, *args))
    _background.add(job)  # keep a reference so the job isn't garbage-collected
    job.add_done_callback(_background.discard)
