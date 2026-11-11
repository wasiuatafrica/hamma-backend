# Hamma API: Heroku → Railway migration guide

Manual, step-by-step. Written 2026-11-11 from an audit of this repo and the live `api-hamma` Heroku app.
**Budget: $8/month for this API.** Scheduled work runs at most every 5 minutes. Costs grow only with traffic.

## 1. What runs today (audited)

| Piece | Today on Heroku | Audit notes |
|---|---|---|
| Web | 1 Basic dyno, Daphne (`bin/start-pgbouncer-stunnel daphne backend.asgi:application`) | Django 6.0.8 + Channels 4.3. Websockets: `ws/notifications/`, `ws/markets-ai/`, `ws/alerts-ai/`, `ws/no-auth-support/`, `ws/admin-support/` |
| Worker + beat | 1 Basic dyno, `celery -A backend worker -B --pool=solo` | Beat uses `DatabaseScheduler`, so the schedules live in Postgres |
| Release | `python manage.py migrate` | On Railway this becomes the pre-deploy command |
| Postgres | essential-0, PG 15.18, **59 MB** | About 16 MB of that is dead `silk_*` profiler data |
| Redis | Redis Cloud 100 MB (`REDISCLOUD_URL`) | Serves as Celery broker, Celery results, cache and the Channels layer. **This add-on also serves FT9ja and Partners. Never delete `api-hamma` before they have moved.** |
| Scheduler | Heroku Scheduler add-on | Its jobs can't be listed from the CLI. See step 0.3 |
| Region | **US** | Railway EU West is closer to Lagos users and to S3 in `eu-north-1` |
| Traffic | ~360k requests/month; p50 26 ms, p95 405 ms | Very light. One web process is enough |

**How Celery is used** (this drives the design):

1. **Scheduled tasks.** 13 are enabled; 2,424 disabled ones are hackathon leftovers.
   - Every 3 min: `competition_returns7`, `calc_tailing_sl`, `process_all_demo_limit_order_task`, `process_all_competition_limit_order_task`, `returns5`
   - Every 5 min: `check_alert`, `update_user_streaks_daily_task`
   - Crons on Africa/Lagos time: classify_assets, tradingview signal, NGX company details, NGX stock sync, trial reminder, backend_cleanup
   - Code also creates one-off `PeriodicTask` rows at runtime, in competition, hackathon, accounts, portfolio, execution, streaks and lock.
2. **Interactive `.delay()` calls** (about 20 call sites). These include the AI chat websockets (`process_market_data2`, `process_alert_data2`), welcome emails, `create_returns`, `create_alert_schedule` and notification updates. These need to run within seconds, not on a 5-minute cycle.

## 2. Railway billing, in short

- **There is no per-product fee.** Postgres, Redis, the web service and cron jobs are all plain containers, billed on the same meters:
  - $10 per GB of RAM per month
  - $20 per vCPU per month
  - $0.15 per GB-month of volume
  - $0.05 per GB of egress
- **A cron job is billed only while its container runs.** Between runs it costs nothing.
- **The plan fee is separate.** Pro is a $20/month minimum per workspace, credited against usage. Hamma's ~$6–8 is part of that $20, so while Hamma is alone in the workspace the bill is still $20. That changes as the other projects move in.

## 3. Target design: three always-on containers plus one 5-minute cron

The always-on Celery worker goes away entirely. That's the biggest saving, about $3–5/month.

```
hamma-api (project, EU West)
├── web       PROCESS=web   Daphne. Runs interactive tasks in-process (eager), in threads for websockets
├── tick      PROCESS=tick  Railway cron "*/5 * * * *": runs due PeriodicTasks, then exits
├── Postgres  Railway template, tuned small
└── Redis     Railway template. Channels layer + cache only (no broker, no results)
```

- **Interactive tasks run inside `web`.** Setting `CELERY_TASK_ALWAYS_EAGER=True` makes every `.delay()` run immediately in the calling process, so no broker or worker is needed.
  - Views and signals: `.delay()` runs inline in the request thread. This adds the task's time to that request. For a welcome email, that's ~0.3 s for SendGrid.
  - The two AI chat consumers are async. An inline call there would freeze the event loop for every user, so they run in a thread pool instead (code in 4.4).
- **Scheduled tasks run in `tick`.** A management command reads `django_celery_beat`'s tables, runs whatever is due, updates `last_run_at`, and exits. It covers interval, crontab and clocked one-off tasks, so the rows the code creates at runtime keep working, at 5-minute resolution.
  - Railway skips a cron run if the previous one is still running.
  - Railway's UTC-only cron is irrelevant here: the `CrontabSchedule` rows keep their own `Africa/Lagos` timezone.
- **All intervals become at least 5 minutes** (step 5.4). Business impact: limit orders and trailing stops are now checked every 5 minutes instead of every 3.

### Expected cost (estimate; RAM is not measured yet, see 0.2)

| Container | Assumed use | $/month | Scales with traffic? |
|---|---|---|---|
| web | 0.22–0.30 GB, 0.03–0.06 vCPU (209 MB measured at startup, see 4.9) | 2.8–4.2 | CPU and egress grow with requests |
| tick (cron) | ~0.2 GB for a few seconds per run; every 5 min at peak, hourly off-peak (see 4.2) | 0.3–0.8 | Grows with users and competitions, not with requests |
| Postgres (tuned) | 0.06–0.10 GB + 0.5 GB volume | 0.7–1.1 | Grows with data |
| Redis | 0.01–0.02 GB | 0.1–0.2 | Grows with websocket users |
| Egress | 5–10 GB | 0.25–0.5 | Yes |
| **Total** | | **≈ 4.2–6.8** | Fits $8. Web memory is the line to watch |

## 4. Code changes (one branch, one PR, before anything is deployed)

**Implemented on branch `railway-migration`.** The snippets below summarize it; the files in the branch are the source of truth.

Everything below is controlled by env vars, so the same commit runs on Heroku unchanged until you set the new vars.

### 4.1 `Dockerfile` (was empty)

```dockerfile
FROM python:3.12-slim-bookworm AS build
COPY --from=ghcr.io/astral-sh/uv:0.12.5 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock ./
# No cache mount: Railway requires service-specific cache ids.
RUN uv sync --frozen --no-dev --no-install-project --no-cache

FROM python:3.12-slim-bookworm
# libcairo2: runtime library for cairosvg/cairocffi
RUN apt-get update && apt-get install -y --no-install-recommends libcairo2 \
    && rm -rf /var/lib/apt/lists/*
RUN useradd -m app
WORKDIR /app
COPY --from=build /app/.venv /app/.venv
# MALLOC_ARENA_MAX=2: stops glibc growing one memory arena per thread.
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    MALLOC_ARENA_MAX=2
COPY --chown=app:app . .
# Build-time key only for collectstatic; the real SECRET_KEY comes from Railway at runtime.
RUN SECRET_KEY=collectstatic-only python manage.py collectstatic --noinput
USER app
CMD ["sh", "bin/start.sh"]
```

`libcairo2` is the runtime library that `cairosvg` needs.

### 4.2 `bin/start.sh` (new). One image, two roles.

`PROCESS=web` starts Daphne. `PROCESS=tick` runs `python manage.py beat_tick`, behind an off-peak gate.

**Off-peak gate.** Railway starts the tick container every 5 minutes, all day. The script checks the clock before loading Django:

| When | What the tick does |
|---|---|
| Weekdays 08:00–17:59 Lagos (07:00–16:59 UTC) | Runs every 5 minutes. This covers NGX trading and the 08:00, 08:10, 17:00 and 17:10 crons |
| Nights and weekends | Runs only in the first 10 minutes of each hour. The other starts exit in under a second, before Python loads |

- Off-peak, a due task can run up to an hour late: one-off competition and email tasks, and the weekend trial reminders (08:10 runs at 09:00, 17:10 at 18:00).
- Market holidays on weekdays still get 5-minute runs. The tasks themselves skip work on holidays.
- Set `TICK_ALWAYS=1` on the `tick` service to run every 5 minutes around the clock.

This cuts full runs from about 8,640 to about 3,600 a month, with one cron service and no locking.

### 4.3 `backend/settings.py`

**Database.** `dj_database_url.config()` always prefers the `DATABASE_URL` env var over `default=`, so use `parse()`. That lets Heroku point at Railway through `DB_URL` during the cutover.

```python
DATABASES = {
    "default": dj_database_url.parse(
        os.environ.get("DB_URL") or os.environ["DATABASE_URL"],
        conn_max_age=int(os.environ.get("DB_CONN_MAX_AGE", "600")),
        conn_health_checks=True,
    )
}
```

**Redis.** Railway exposes `REDIS_URL`; Heroku exposes `REDISCLOUD_URL`. Replace the production `else:` branch:

```python
else:
    REDIS_URL = os.environ.get("REDIS_URL") or os.environ.get("REDISCLOUD_URL")
    CELERY_BROKER_URL = REDIS_URL
    CELERY_RESULT_BACKEND = REDIS_URL
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {"hosts": [REDIS_URL]},
        },
    }
```

**Celery.** When `CELERY_EAGER=True`, there's no broker and no worker: `.delay()` runs in-process. No code reads task results, and there are no `countdown`/`eta`/`retry` calls, so eager mode is safe.

```python
CELERY_TASK_ALWAYS_EAGER = os.environ.get("CELERY_EAGER") == "True"
CELERY_TASK_EAGER_PROPAGATES = False     # a failing task must not 500 the request
CELERY_TASK_IGNORE_RESULT = True
```

### 4.4 Run the AI chat tasks off the event loop

Implemented in `backend/threads.py`, which is called from `MarketConsumer2.receive` (`execution/consumers.py`) and `AlertConsumer2.receive` (`portfolio/consumers.py`):

```python
dispatch(process_market_data2, message, self.conversation_id, self.user_id, self.channel_name)
```

How `dispatch` behaves:

- **Eager mode (`CELERY_EAGER=True`, Railway):** it starts the task body in a pool thread and returns immediately, so the call is fire-and-forget like `.delay()`. That matters because the task replies through the channel layer, and a consumer only delivers those replies after `receive()` returns. Awaiting the task would hold every reply until the end. Each chat gets its own thread (`thread_sensitive=False`, pool capped by `ASGI_THREADS`). DB connections are closed around the call.
- **Otherwise (Heroku today):** it still calls `.delay()`, so behavior is unchanged until you set the variable.

### 4.5 `beat_tick` command: `backend/management/commands/beat_tick.py`

`"backend"` is added to `INSTALLED_APPS` so the command is found.

Each run:
1. Loads every enabled `PeriodicTask`.
2. Runs the due ones in-process, with `.apply()`.
3. Updates `last_run_at` and `total_run_count`, and disables one-off and clocked tasks after their run.
4. Exits.

Failures and unregistered tasks are logged; they don't stop the run. Interval tasks run before crontab tasks, so a slow NGX sync can't delay order processing.

When a task counts as due:

| Schedule | Rule |
|---|---|
| Interval | Due when `now - last_run_at >= every - 60 s`. The 60-second slack absorbs cron start jitter; without it a 5-minute task drifts to every 10 minutes |
| Crontab | Due once its slot has passed, with **no slack**. Running early would record a `last_run_at` before the slot, and the next tick would run it again. A crontab task seen for the first time starts from now and doesn't replay history. Each row keeps its own timezone (`Africa/Lagos`) |
| Clocked one-off | Due within 60 s of its time, then disabled |

Commands:
- `python manage.py beat_tick --dry-run` lists what's due without running anything.
- `python manage.py beat_tick` runs it.

Tested locally against SQLite:
- Interval drift, not-due tasks, crontab first sight and due, early hourly slot not run, clocked one-off disabled after its run, failing task, unregistered task, immediate re-run, eager `.delay()`.
- `dispatch` returned in 0 ms and ran 2 chats in parallel.

### 4.5b Runtime intervals raised to 5 minutes

`execution/views.py` (limit orders) and `execution/tasks.py` (2 sites) created `IntervalSchedule(every=3)`. They now use `every=5`.

### 4.6 Health check (`backend/urls.py`)

```python
from django.http import HttpResponse
urlpatterns = [path("healthz", lambda r: HttpResponse("ok")), *urlpatterns]
```

### 4.7 `.dockerignore` (currently empty, so the 617 MB `.venv` and user CSVs would ship)

```
.git
.venv
__pycache__
*.pyc
db.sqlite3
staticfiles
*.csv
*.xlsx
.cursor
.vscode
docs
react
lambda
tradingView-API
market_data_system
*.md
```

Keep `execution/symbols.json` and `portfolio/data/` in the image. Check whether any runtime code reads a root-level `.json` before you exclude it.

### 4.8 Railway config as code

`railway/web.toml`:

```toml
[build]
builder = "DOCKERFILE"
dockerfilePath = "Dockerfile"

[deploy]
preDeployCommand = ["python manage.py migrate --noinput"]
healthcheckPath = "/healthz"
healthcheckTimeout = 120
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 10
numReplicas = 1
sleepApplication = false
```

`railway/tick.toml`:

```toml
[build]
builder = "DOCKERFILE"
dockerfilePath = "Dockerfile"

[deploy]
cronSchedule = "*/5 * * * *"
restartPolicyType = "NEVER"
```

Only `web` runs migrations.

### 4.9 Memory and query optimizations (on the branch)

**Memory.** Measured locally, loading the app as Daphne does:

| | Before | After |
|---|---|---|
| Memory after startup and all views loaded | 302 MB | 209 MB |
| Import time | 4.7 s | 2.2 s |

- **scikit-learn (79 MB)** is imported inside `ml_based_recommendation` in `tradingai/utils.py`. The unused `RandomForestClassifier` import is removed.
- **openai (19 MB)** loads on first use, through `backend/lazy.py`. `OpenAI(...)` is a drop-in factory, and `LazyOpenAIClient()` replaces the module-level `client = OpenAI()` in `execution/tasks.py`, `portfolio/tasks.py` and `supportwithemail/task.py`.
- Once a feature is used, its library stays loaded until the next restart. So memory rises by 79 MB after the first trade recommendation and 19 MB after the first AI chat.
- `MALLOC_ARENA_MAX=2` is set in the Dockerfile. It stops glibc growing one memory arena per thread.
- pandas (44 MB) is still imported at startup, at the top of 16 files. Lazy-loading it is a separate pass.

**Queries.** Each rewrite was run against the original code on identical SQLite fixtures and produced identical rows.

| Task | Change | Queries per run |
|---|---|---|
| Streak checker (`streaks/streak_utils.py` `process_accounts`) | Three set queries find who traded today, who is already recorded and who has a streak record. Only accounts with something to record are processed | 721 → 4 for 120 idle accounts. In production that is roughly 4,300 → a handful |
| `daily_returns7` and `competition_daily_returns7` (`execution/utils.py`) | Loop only over portfolios that closed a trade today, found with one query. Stock symbols load with the positions | One query replaces one per portfolio (about 1,074 for demo) |
| Stock list (`portfolio/views.py`, 2 views) | Watchlist symbols come from one query | One query replaces one per watchlist row |

**Celery binding.** `backend/asgi.py` loads and binds every task at startup when `CELERY_EAGER=True`. Celery binds tasks lazily on first use, and that step isn't thread-safe: two chats arriving together on an unbound task failed with `'NoneType' object has no attribute 'push'`. Binding at startup removes the race, and `dispatch` also binds on the event-loop thread before handing off.

**Known and unchanged:** the end-of-day streak reset in `process_accounts` only fires if the task runs at exactly 16:00:00 Lagos, because the trading-time window ends at 16:00:00 and the reset needs the time to be 16:00:00 or later. In practice a broken streak is corrected on the user's next trade. This behaviour is the same before and after the rewrite.

### 4.10 Dependency upgrade (2026-11-11)

**The lockfile on `main` has 74 known advisories across 11 packages**, including Twisted (the server under Daphne), Pillow, Django REST framework and pymongo. The lockfile on this branch has none (checked with `pip-audit`). Deploy from this branch's `uv.lock`, not `main`'s.

**Upgraded: 37 packages.** The ones that matter for security:

| Package | From → to | Why |
|---|---|---|
| Django | 6.0.8 → 6.0.10 | Both are security releases: 10 CVEs, including a denial-of-service in HTTP header parsing that needs no login. `pip-audit` did not flag these yet |
| django-allauth, django-otp | 65.19.4 → 65.21.1, 1.7.3 → 1.7.5 | Login and 2FA libraries |
| cryptography, pyjwt, truststore | patch releases | Token signing and TLS |
| asgiref, websockets, anyio, httpx2 | minor and patch releases | The async and HTTP layers under Daphne and the OpenAI client |
| sqlparse, markupsafe, lxml-html-clean, charset-normalizer | patch releases | Parsers that handle untrusted input |

The rest are patch releases of supporting libraries (boto3, numpy, pytz and tzdata, amqp, billiard and others).

**Floors added in `pyproject.toml`** so a later re-lock can't go back below the fixed versions: Django 6.0.10, Django REST framework 3.18.2, Pillow 13.0.0, pymongo 4.18.3, and (as constraints) Twisted 26.10.0 and autobahn 26.10.1.

**Held back on purpose:**

| Package | Latest | Why it's held |
|---|---|---|
| celery, kombu | 5.7.0 | Six days old, a new minor release aimed at workflows and workers, which this app doesn't use on Railway. `beat_tick` and eager mode depend on Celery internals. Revisit at 5.7.1 |
| pandas | 3.1.1 | New minor release. The returns calculations depend on it and no security fix is known |
| openai, pydantic | 3.49.0, 2.14.3 | Thirty minor releases ahead, the newest one day old. The chat code uses the Assistants API (`client.beta.threads`), so this needs its own tested upgrade |
| drf-yasg | 1.21.18 | Adds six new packages to the image for the API docs page |
| gunicorn | 27.0.0 | One day old and unused: the server is Daphne |
| soupsieve, w3lib | 4.1, 2.6.0 | A major version and a release that pulls in a six-day-old package (`frostwork`) |
| boto3, svglib, jiter, click, filelock, cbor2 | — | Newer releases are under a week old |

**No breaking changes were found.** On the upgraded versions:
- `manage.py check` is clean, no new migrations are pending, and no model changes are detected.
- The 64 unit tests give the same result as before the upgrade and as on `main`: 57 pass and 7 fail. The 7 failures already exist on `main`.
- The `beat_tick`, chat dispatch, streak and returns tests all pass, and the streak and returns output is identical before and after.

**To upgrade again later**, wait until a release is at least a week old, then upgrade it by name and re-run the checks:

```bash
uv lock --upgrade-package celery==5.7.1 --upgrade-package kombu
```

**Unused dependencies worth removing later:** `gunicorn`, `django-sms` and `django-silk` (local profiling only) are not imported by the deployed app.

---

## 5. Step-by-step

### Step 0. Before touching Railway

1. **Rotate the GitHub token** that is embedded in `origin` in `.git/config`. Revoke it on GitHub, then:
   ```bash
   git remote set-url origin https://github.com/wasiuatafrica/hamma-backend.git
   ```
2. **(Optional, 24 h) Measure real RAM** to confirm the budget.
   ```bash
   heroku labs:enable log-runtime-metrics -a api-hamma && heroku ps:restart -a api-hamma
   ```
   The next day:
   ```bash
   heroku logs -a api-hamma -n 1500 | grep memory_total
   ```
3. **Heroku Scheduler jobs.** Open the add-on and move each job into `django_celery_beat` (Django admin → Periodic tasks). `tick` will then run them.
   ```bash
   heroku addons:open scheduler -a api-hamma
   ```
4. **Install a Postgres client**, version 15 or newer:
   ```bash
   sudo apt install postgresql-client
   ```
5. **Merge the PR from section 4 and deploy it to Heroku** without setting any new env vars. This proves the changes are harmless.
   ```bash
   git push heroku main
   ```

### Step 1. Workspace guardrails (before creating any service)

1. **Usage alert and hard limit.** Workspace → Settings → Usage: alert at **$25**, hard limit at **$40**.
   - The alert sits just above the $20 Pro minimum, so any real overrun shows up quickly.
   - The hard limit is a last resort: it takes every service in the workspace offline. Raise both as other projects move in.
2. **PR environments off.** Project → Settings → Environments. Each preview would be a billed copy of every service.

### Step 2. Data services

1. **Create the project.** New project `hamma-api`, region **EU West**.
2. **PostgreSQL.** + New → Database → PostgreSQL.
   - Settings → Backups → enable daily.
   - Then shrink its memory footprint. The database is 59 MB, so the defaults (128 MB `shared_buffers`, 100 connections) are oversized. Connect with the public URL and run:
     ```sql
     ALTER SYSTEM SET shared_buffers = '32MB';
     ALTER SYSTEM SET max_connections = 30;
     ALTER SYSTEM SET work_mem = '2MB';
     ALTER SYSTEM SET maintenance_work_mem = '16MB';
     ALTER SYSTEM SET effective_cache_size = '128MB';
     ```
   - Restart the Postgres service. These settings live on the volume, so they survive redeploys.
3. **Redis.** + New → Database → Redis.
   - Settings → Deploy → Custom start command: keep the template's command and **append** `--maxmemory 32mb --maxmemory-policy allkeys-lru --save ""`.
   - With no broker and no results, Redis holds only the cache and Channels messages, both of which are disposable. So LRU eviction is safe, and turning off snapshots (`--save ""`) saves disk writes.

### Step 3. App services

Both come from **+ New → GitHub repo → wasiuatafrica/hamma-backend** (`main`). Name them `web` and `tick`.

**Shared variables** (Project → Settings → Shared variables):

1. Export Heroku's config:
   ```bash
   heroku config -a api-hamma --shell > /tmp/hamma.env
   ```
2. Paste it into the Raw Editor.
3. Delete `DATABASE_URL`, `REDISCLOUD_URL` and `server`. `server` must never be `local`.
4. Set `DEBUG=False` and `CELERY_EAGER=True`.
5. Remove the export: `rm /tmp/hamma.env`.

> `SECRET_KEY` must be **identical** to Heroku's. It signs the JWTs, so a different key logs every user out.

| Variable | web | tick |
|---|---|---|
| shared variables | all | all |
| `PROCESS` | `web` | `tick` |
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` (private network, no egress) | same |
| `REDIS_URL` | `${{Redis.REDIS_URL}}` | same |
| `DB_CONN_MAX_AGE` | `0` | `0` |
| `ASGI_THREADS` | `4` | — |
| `TICK_ALWAYS` | — | unset (set `1` to disable the off-peak gate) |

`DB_CONN_MAX_AGE=0` on web avoids connection leaks under ASGI.

`ASGI_THREADS=4` caps the thread pool. Railway hosts show many CPUs, and the default pool size would scale up to 32 threads. Four is enough at this traffic; raise it if AI chats start queueing.

| Setting | web | tick |
|---|---|---|
| Config-as-code path | `railway/web.toml` | `railway/tick.toml` |
| Replicas | 1 | 1 (cron) |
| Serverless / sleep | **off** (websockets and polling would wake it constantly anyway) | n/a |
| Resource limits | **0.5 vCPU / 512 MB** | 0.5 vCPU / 512 MB |
| Networking | generate a `*.up.railway.app` domain | none |

The resource limits are the budget guard. They cap web at worst at ~$15/month, and Railway restarts the service on out-of-memory instead of letting the bill grow. Normal use is ~$4.

**Deploy `web` now. Leave `tick` paused** (Settings → Cron → disable) until cutover, so that it and Heroku's beat never both run the tasks.

### Step 4. Moving the data (manual, kept minimal)

The app deploys separately from Heroku, so the data moves by hand with `pg_dump` / `pg_restore`.

- **Redis needs nothing.** Queues, cache and Channels messages are all transient.
- **Postgres: copy only what's alive.** Don't modify Heroku's database; skip the dead data at dump time and clean up on Railway.

1. Dump, skipping the dead data:
   ```bash
   pg_dump "$(heroku config:get DATABASE_URL -a api-hamma)" -Fc --no-owner --no-acl \
     --exclude-table-data='silk_*' --exclude-table-data='django_session' \
     -f hamma.dump
   ```
   - The `silk_*` tables hold ~16 MB of dead profiler data.
   - `django_session` only holds Django admin sessions. API users use JWT and stay logged in.
2. Restore. Copy `DATABASE_PUBLIC_URL` from the Postgres service:
   ```bash
   pg_restore --no-owner --no-acl --clean --if-exists -j 4 -d "$RAILWAY_PG_PUBLIC_URL" hamma.dump
   ```
   Errors about `heroku_ext` or `pg_stat_statements` are harmless.
3. Clean up on Railway, using `psql "$RAILWAY_PG_PUBLIC_URL"`:
   ```sql
   DROP TABLE IF EXISTS silk_request, silk_response, silk_sqlquery, silk_profile, silk_profile_queries CASCADE;
   DELETE FROM django_celery_beat_periodictask WHERE NOT enabled;   -- 2,424 dead one-offs
   -- schedules no task points at any more (about 2,000 crontab rows)
   DELETE FROM django_celery_beat_crontabschedule c WHERE NOT EXISTS
     (SELECT 1 FROM django_celery_beat_periodictask p WHERE p.crontab_id = c.id);
   DELETE FROM django_celery_beat_clockedschedule c WHERE NOT EXISTS
     (SELECT 1 FROM django_celery_beat_periodictask p WHERE p.clocked_id = c.id);
   ```
4. **Raise every interval to 5 minutes or more.** Run this in Railway's web service shell (`railway ssh` or `railway run python manage.py shell`):
   ```python
   from django_celery_beat.models import PeriodicTask, IntervalSchedule as I
   five, _ = I.objects.get_or_create(every=5, period=I.MINUTES)
   PeriodicTask.objects.filter(interval__period=I.MINUTES, interval__every__lt=5).update(interval=five)
   PeriodicTask.objects.filter(interval__period=I.SECONDS).update(interval=five)
   ```
   The code that creates schedules at runtime already uses 5 minutes on this branch (4.5b).
5. **Rehearse first.** Do steps 1–4 once while Heroku is still live, then test against `https://<web>.up.railway.app`:
   - `/healthz`
   - `/auth/login/`
   - `/portfolio/stocks/`
   - `/portfolio/market-status/`
   - Django admin login
   - the `ws/markets-ai/` chat, which must reply within seconds
   - an image upload
   - a manual tick: `railway run python manage.py beat_tick --dry-run`
   
   Time the dump and restore. At ~43 MB it should take under a minute.

### Step 5. Domain (before cutover, no user impact)

No frontend uses `worldclass.gohamma.com` today, and its HTTPS is broken, so the domain can move ahead of the cutover.

1. In `web`: Settings → Networking → Custom domain → `worldclass.gohamma.com`.
2. In Route 53, add the CNAME Railway gives you (and the `_railway-verify` TXT record if it asks for one).
3. Wait for the certificate, then check `https://worldclass.gohamma.com/healthz`.

### Step 6. Cutover (~15 min, quiet time, e.g. Sunday evening WAT)

1. **Stop Heroku's beat:**
   ```bash
   heroku ps:scale worker=0 -a api-hamma
   ```
2. **Stop writes:**
   ```bash
   heroku maintenance:on -a api-hamma
   ```
3. **Final copy:** repeat step 4.1–4.4 (dump, restore with `--clean`, cleanup, intervals).
4. **Bridge.** Point Heroku's web dyno at Railway's data, with eager tasks:
   ```bash
   heroku config:set DB_URL="$RAILWAY_PG_PUBLIC_URL" REDIS_URL="$RAILWAY_REDIS_PUBLIC_URL" CELERY_EAGER=True -a api-hamma
   ```
5. **Enable `tick`** on Railway (Settings → Cron). Check that its first run logs `tick: N due`.
6. **Reopen:**
   ```bash
   heroku maintenance:off -a api-hamma
   ```
7. **Switch frontends** to `https://worldclass.gohamma.com/` and deploy them (section 7).

After step 4, old clients that still call the herokuapp URL keep working on the same data. Keep this bridge short: every Heroku query now crosses from the US to the EU (~90 ms each), and that traffic is billed as Railway egress.

**Rollback** (before the frontends switch):
```bash
heroku config:unset DB_URL REDIS_URL CELERY_EAGER -a api-hamma
```
```bash
heroku ps:scale worker=1 -a api-hamma
```
Then pause `tick`, and dump Railway back into Heroku if there were writes since cutover.

### Step 7. After cutover

- **Days 1–3:** watch web memory against the 512 MB limit (expect about 210 MB after a restart, rising as AI features are used), and check tick run times in the cron logs (each run should take well under 5 minutes). Compare the Usage page against section 3.
- **When herokuapp traffic stops:** scale Heroku's web dyno to 0. Two weeks later, run `heroku addons:destroy heroku-postgresql -a api-hamma`.
- **Keep the `api-hamma` app** until FT9ja and Partners are off its Redis Cloud add-on.

---

## 6. Potential issues and fixes

| # | Issue | Fix |
|---|---|---|
| 1 | **Process and thread counts default to CPU count.** Railway hosts show many CPUs | One Daphne process, `ASGI_THREADS=4`, no Celery worker at all |
| 2 | **Memory creep.** Every GB held for a month costs $10 | 512 MB resource limit on web (OOM restarts instead of a growing bill). scikit-learn and openai are lazy-loaded (4.9). Optional next pass: lazy-import `pandas` to save ~44 MB |
| 3 | **Preview environments.** Each is a full billed copy | Turn PR environments off (step 1.2) |
| 4 | **The web service sleeping** | Serverless off. With polling and websockets it would never sleep anyway |
| 5 | **Tasks running twice** (Heroku beat + tick) | Scale Heroku's worker to 0 *before* enabling tick (cutover 1 → 5). Keep tick paused until then |
| 6 | **Interval drift under cron.** A 5-min task can slip to every 10 min | `SLACK` = 60 s in `beat_tick` |
| 7 | **A tick run longer than 5 min.** Railway skips the next run | Frequent tasks run first. Watch the logged durations. If NGX sync or classify_assets get slow, give them their own cron service at a quiet time (costs pennies) |
| 8 | **Eager tasks slow requests** (welcome email, `create_returns`) | Usually under a second. If one becomes slow, move it to a thread with `backend.threads.run_in_thread` |
| 9 | **The AI chat blocking the event loop** | `dispatch` (4.4). Never call an eager `.delay()` from an `async def`; use `dispatch` |
| 10 | **DB connections under ASGI and threads** | `DB_CONN_MAX_AGE=0`, `close_old_connections()` around threaded work, and Postgres `max_connections=30` |
| 11 | **`dj_database_url.config()` ignores `default=`** | Use `parse()` (4.3); otherwise `DB_URL` silently does nothing |
| 12 | **Heroku-only wiring** (pgbouncer wrapper, `release:` phase, `REDISCLOUD_URL`) | `start.sh`, `preDeployCommand`, and the `REDIS_URL` fallback |
| 13 | **Redis growth** | `maxmemory 32mb` with `allkeys-lru`; no broker or results are stored |
| 14 | **Egress** | Private URLs between services, gzip is already on, keep the bridge short |
| 15 | **Postgres is a single container** with no point-in-time restore | Daily backups. Test one restore before destroying Heroku Postgres |
| 16 | **The hard limit takes everything offline** | Alert at $25, limit at $40. Review whenever a project joins the workspace |
| 17 | **`SECRET_KEY` mismatch logs everyone out** | Copy it unchanged |
| 18 | **Frontends hardcode the herokuapp URL** | Use the bridge, and make the URLs env-driven (section 7) |
| 19 | **Tightening `ALLOWED_HOSTS` later** | Include `worldclass.gohamma.com`, `.up.railway.app` and `healthcheck.railway.app` |
| 20 | **Websockets drop on every redeploy** | Clients must reconnect with backoff |
| 21 | **Build failures** | `libcairo2` is in the Dockerfile and `.dockerignore` is in place. Add any missing system lib to the runtime `apt-get` line |
| 22 | **US → EU region change** | Check the Atlas region for `MONGO_STRING`. Cron times are unaffected (`Africa/Lagos`) |
| 23 | **Security: CORS allows any origin with credentials** while auth uses cookie JWTs | After migration, set `CORS_ALLOW_ALL_ORIGINS=False` and rely on the allowlist. Add worldclass, leaderboard, competition and refer to it first |
| 24 | **Security: repo hygiene.** A GitHub token is in the git remote, and PII CSV/XLSX files are tracked | Rotate the token. `git rm --cached` the files and gitignore them. Consider `git filter-repo` |
| 25 | **Unknown Heroku Scheduler jobs** | Step 0.3 |
| 26 | **The Redis Cloud add-on is shared** | Delete `api-hamma` last |
| 27 | **Off-peak tasks run up to an hour late** (nights, weekends) | Expected with the off-peak gate (4.2). Set `TICK_ALWAYS=1` on `tick` if a competition or campaign needs 5-minute timing at the weekend |
| 28 | **Celery's lazy task binding isn't thread-safe** in eager mode | Tasks are bound at startup in `backend/asgi.py` (4.9). Start chat tasks with `dispatch`, never by calling a task from a new thread yourself |

## 7. Frontend follow-ups

- **`Anyon-user-dashboard`:** replace the hardcoded `https://api-hamma-f0bcaabf77ea.herokuapp.com/` in `src/axios.js`, `SupportChatbot.js` and `ResetPassword.js` with `process.env.REACT_APP_API_BASE_URL`, set to `https://worldclass.gohamma.com/`.
- **`Anyon-admin-dashboard`** and the leaderboard, competition, refer and waitlist apps: grep each for `api-hamma-f0bcaabf77ea` and make the same change.
- **`tradingview-realtime-11e3ea0312f6.herokuapp.com`** is a separate Heroku app missing from the inventory. It needs its own migration entry.
