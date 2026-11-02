# Performance Audit — Hamma

Audit date: 2026-09-29  
Scope: this repository (Django/Channels/Celery API, MongoDB market data, DynamoDB notifications, Heroku `Procfile`).  
Method: static review of request paths, workers, queries, and data growth. No production metrics, `EXPLAIN` plans, or load-test traces were available. Findings that depend on which Celery Beat rows are enabled, dyno counts, or collection sizes are marked assumption-based.

Runtime evidence that would confirm or reject the largest hypotheses is listed under each finding.

---

## 1. Executive Performance Summary

| Severity | Count |
|---|---:|
| Critical | 4 |
| High | 8 |
| Medium | 7 |
| Low | 3 |

- **Primary bottleneck:** one Celery process (`--pool=solo` plus embedded Beat) serializes every background job, including multi-second sleeps and OpenAI polling, while trading-hours jobs scan every user, portfolio, or pending order.
- **Primary scalability risk:** leaderboard and clan APIs recompute closed-position profit for every portfolio once per clan. Cost is roughly `clans × portfolios × closed positions` per request, and the hot endpoint is unauthenticated.
- **Primary memory risk:** chart history documents and `simple_history` tables grow for the life of the process and the life of the data. Mongo chart updates load and rewrite the whole array. Admin analytics and “paginate after serialize” endpoints materialize full tables in the web process.
- **Primary CPU risk:** the Daphne process is a single event loop. `time.sleep(1)` and synchronous DynamoDB/ORM calls inside async WebSocket handlers stall every connection on that process.
- **Primary database risk:** scheduled jobs issue one or more queries per user or portfolio (`User.objects.all()` loops). Position tables have no explicit indexes on `status`, `portfolio`, or `closed_at`. `conn_max_age=600` sits in front of PgBouncer.
- **Primary concurrency risk:** web concurrency and worker concurrency are both effectively 1. Adding HTTP concurrency without raising the database pool, or adding worker dynos without a task time limit, pushes load into Postgres, Mongo, and Redis.
- **Primary cost-amplification risk:** each limit order inserts a Beat row that runs every 3 minutes; leaderboard cache tasks insert another Beat row every run; each chat turn can hold the only worker for up to ~30 seconds of OpenAI polling plus intentional sleeps. One client action becomes recurring shared-infrastructure work.

### Categories checked

| Area | Result |
|---|---|
| Backend APIs, ORM, Celery, Channels | Reviewed |
| MongoDB market/chart data | Reviewed |
| DynamoDB notifications | Reviewed |
| Redis (broker, result backend, cache, channel layer) | Reviewed; one deployment URL |
| Object storage (S3 presign) | Reviewed |
| Postgres via `dj_database_url` + PgBouncer stunnel | Reviewed from settings and `Procfile` |
| Frontend / browser bundles | Not in this repository. Dashboards are separate Netlify apps. |
| GraphQL | Not present |
| Elasticsearch / dedicated search | Not present |
| Kubernetes / HPA | Not present. Process model is Heroku (`Procfile`). |
| Mobile / native | Not present |
| WebSocket broadcast fan-out of O(connections²) | Not present. Groups are per user or per conversation. The failure mode is event-loop blocking, not broadcast complexity. |

---

## 2. System Performance Model

### Process model

`Procfile`:

- `web`: PgBouncer stunnel, then **one** Daphne process (`backend.asgi:application`). No worker count is set. Daphne’s default is one process and one asyncio loop. HTTP and WebSockets share it.
- `worker`: `celery -A backend worker -B -l warning --pool=solo`. Beat and task execution share **one thread**. A running task delays the scheduler. A slow scheduler delays every queued task.
- `release`: `migrate` on every release. Long migrations reduce capacity during deploy. No migration in this review was timed.

### Synchronous request path

Browser/app → Daphne → Django view → Postgres and/or Mongo and/or DynamoDB and/or S3 presign → JSON response.

There is no DRF throttle class, no global request-body cap beyond Django defaults, no view timeout, and no admission control. `REST_FRAMEWORK` sets auth only (`backend/settings.py` around 190–198).

### Asynchronous path

WebSocket message or HTTP trade → `task.delay()` → Redis → the solo worker.

Limit orders also insert `django_celery_beat.PeriodicTask` rows (every 3 minutes, one row per order). Those rows are a second producer into the same solo worker.

### Shared resources (global bottlenecks)

| Resource | Who shares it | What saturates first |
|---|---|---|
| Daphne event loop | all HTTP + all WebSockets on the web dyno | any `time.sleep` or sync I/O in an async consumer |
| Solo Celery worker | Beat, returns jobs, limit orders, alerts, AI chat, chart updates, prop analysis | the longest task |
| Redis (`REDISCLOUD_URL`) | broker, result backend, Django cache, Channels layer | large channel messages, result keys, cache stampedes |
| Postgres | web threads (`CONN_MAX_AGE=600`) and the worker | connection slots and sequential scans from per-user loops |
| Mongo `livelake3` | price reads on the request path and chart jobs | latest-document fetches and the per-symbol aggregation |
| DynamoDB notification table | every connect and every trade notification | partition reads that grow with messages per user |
| OpenAI | market/alert chat tasks | worker occupancy, token cost |

### Work-amplification relationships

```
1 limit order
  → 1 PeriodicTask every 3 minutes
  → each run: Postgres row + Mongo find_one of the full latest price document
  → until the order fills or expires (hours, or “week” time-in-force)

1 unauthenticated TopClans request during a live competition
  → 1 full profit scan of every active competition portfolio
  → then 1 full scan again per ranked clan (profit_comparison → get_leaderboard)
  → response is then sliced to 3 clans

1 WebSocket chat message that reaches the model
  → up to 30s of OpenAI polling on the only worker
  → plus 4s of timer.sleep inside order placement
  → other jobs (stops, limit orders, returns) wait behind it

1 symbol in update_live_1m
  → aggregation that $objectToArray’s every merged price document
  → repeated once per active stock, serially, on the only worker
```

### Scaling dimensions

Users, portfolios per user, closed positions per portfolio, pending limit orders, clans, active symbols, merged price documents per day, chart bars per symbol, notification items per user, Beat rows, history-table rows, web dynos, worker dynos.

---

## 3. Complexity Hotspots

| Location | Code Path | Complexity | Scaling Variable | Why It Matters |
|---|---|---:|---|---|
| `competition/views.py` `TopClans.get` + `Clan.profit_comparison` | Full portfolio scan, then `get_leaderboard()` once per clan | **O(C × P × T)** | clans C, portfolios P, closed trades T | One public request repeats the full profit scan per clan. Confirmed O(n²)-class in portfolios when C grows with P. |
| `competition/views.py` `ClanViewSet` + `ClanSerializer` | Same property per clan, plus full M2M `member` list | **O(C × P × T)** on cache miss | clans, members | `cache_page` hides it for 2 hours. Expiry or `retrieve` pays the full cost. |
| `streaks/tasks.py` `cache_regular_leaderboard` | 2 `COUNT` queries per user, then inserts another Beat task | **O(U)** queries per run, **O(runs)** Beat rows | users U, uptime | Query count and scheduler load both grow. |
| `execution/utils.py` `daily_returns7` | Every demo portfolio, then every closed position into pandas | **O(P × T)** time, **O(T)** RAM per portfolio that traded today | portfolios, lifetime closed trades | Recomputes lifetime history to store one daily number. |
| `execution/utils.py` `daily_returns5` | Same, plus `TvDatafeed().get_hist` inside the portfolio loop | **O(P)** external calls | portfolios that closed today | Network amplification if this task is still scheduled. |
| `execution/tasks.py` `update_latest_cumulative_returns` | All users, then all historical daily-return rows | **O(U × D)** | users, days of history D | Grows with uptime even if user count is flat. |
| `execution/tasks.py` `update_live_1m` | Per symbol, aggregation over the merged collection | **O(S × D)** documents touched | symbols S, price docs D | Runs on the solo worker. |
| `execution/tasks.py` `update_document` | Load chart arrays, extend, `$set` whole document | **O(B)** time and space per symbol | bars B, unbounded | Approaches Mongo’s 16 MB document cap. |
| `execution/tasks.py` `process_all_*_limit_order_task` | One price fetch and trade check per pending order | **O(pending)** serial | pending orders | Each order may also have its own 3-minute Beat task. |
| `portfolio/utils.py` `get_mini_data` | `list_collection_names` then 27 docs per collection | **O(collections)** | symbols stored as collections | Public `mini-chart/` endpoint. |
| `anyon/views.py` `AnalyticsView` | Load all positions, sum in Python | **O(rows)** RAM and CPU | all demo + competition positions | Admin, but one request can pin the web process. |
| `portfolio/utils.py` `get_price` / `get_stockdata2` | `find_one` latest full document | **O(document size)** per call | fields × symbols in the latest doc | Cheap lookup of `_id`, expensive payload. Multiplied by callers. |

No confirmed exponential, factorial, or catastrophic-regex hot path was found in the trading request path. OpenAI tool-call fan-out is bounded by the assistant’s tool list and a 30-second poll cap, not by combinatorial search in this code.

### What the quadratic leaderboard does at size

Assume average closed trades per portfolio `T = 50`, and one query per portfolio that returns those rows.

| Portfolios P | Clans C on the live board | Portfolio queries per TopClans request | Row reads (approx.) |
|---:|---:|---:|---:|
| 100 | 20 | 100 + 20×100 = 2,100 | ~105,000 |
| 1,000 | 100 | 1,000 + 100×1,000 = 101,000 | ~5,050,000 |
| 10,000 | 500 | 10,000 + 500×10,000 = 5,010,000 | ~250,000,000 |

`TopClans` sorts clans and **then** attaches `profit_comparison` for every ranked clan, and only afterwards slices to 3 (`competition/views.py` 2584–2600). The slice does not reduce the work.

---

## 4. Detailed Findings

### 4.1 Single Daphne process blocks on WebSocket sleeps and sync I/O

**Severity:** Critical  
**Confidence:** Confirmed (code and `Procfile`). Impact magnitude is Likely until event-loop lag is measured.  
**Category:** Concurrency / latency  
**Affected Component:** `Procfile` line 2; `execution/consumers.py` `MarketConsumer.receive`; `portfolio/consumers.py` `AlertConsumer.receive`; `notifications/consumers.py`

### Evidence

```2:3:Procfile
web: bin/start-pgbouncer-stunnel daphne backend.asgi:application --port $PORT --bind 0.0.0.0 -v1
worker: celery -A backend worker -B -l warning --pool=solo
```

```83:99:execution/consumers.py
    async def connect(self):
        await self.accept()
        await self.initialize()
        ...
        history = await self.get_messages(self.conversation)
        if history:
            await self.send_message({'message': history})
```

```145:151:execution/consumers.py
            else:
                response = 'Processing your order...'
                process_market_data.delay(...)
        time.sleep(1)
```

`notifications/consumers.py` calls `get_notifications` and `update_notification` directly from `async def` methods (lines 35 and 50–54). Those functions perform synchronous DynamoDB I/O (`notifications/utils.py` 42–76).

### Description

`time.sleep` inside `async def receive` blocks the asyncio loop. Daphne is not configured with extra processes. While the loop is blocked, that dyno cannot read new HTTP requests, send WebSocket frames, or complete disconnects.

`accept()` runs before token validation. A client can open sockets, then stall the loop, without a valid user. `get_messages` loads every `Message` in the conversation into a list with no limit (`execution/consumers.py` 42–49).

### Complexity

- Time: O(1) sleep plus O(history) on connect.
- Space: O(messages in the room) per connect.
- Scaling variable: concurrent sockets, message rate, conversation length.

### Trigger

Any WebSocket message on the market or alert consumer. A tight reconnect or message loop from one client is enough.

### Scaling Behavior

One message costs about 1 second of **global** stall on that dyno, independent of how idle the CPU is. Ten overlapping sends do not overlap; they queue on the loop, so 10 messages ≈ 10 seconds of freeze plus the DynamoDB/ORM time on the notification socket.

### Failure Mode

Latency spike for every user on the dyno, heartbeat timeouts, reconnect storm, which issues more `accept()` calls.

### Estimated Impact

Chatty clients at 10 messages/s can keep the loop busy indefinitely. HTTP p99 on that dyno tracks WebSocket message rate, not Django view cost.

### How to Verify

Instrument `asyncio` loop lag (or `django-prometheus` / a 50 ms heartbeat task). Open one socket, send 20 messages, and measure an unrelated `GET` latency on the same dyno. Expect ~1 s stalls.

### Recommended Fix

Delete the sleeps. Move DynamoDB and ORM work to `database_sync_to_async` / a threadpool only where it does not hold the loop, and do not `sleep` there either. Reject the socket before `accept()` when the token is missing. Cap history (last N messages). Run more than one Daphne process only after the loop no longer blocks; extra processes multiply Postgres connections (`CONN_MAX_AGE`).

### Trade-offs

Removing the 1 s delay changes the bot’s pacing. Auth-before-accept drops unauthenticated browsers that currently connect and then fail during `initialize`.

---

### 4.2 Solo Celery worker plus embedded Beat, with blocking tasks and no time limit

**Severity:** Critical  
**Confidence:** Confirmed for the process model and the blocking calls. Which Beat rows are enabled is assumption-based.  
**Category:** Queue / throughput / reliability under load  
**Affected Component:** `Procfile`; `backend/celery.py`; `backend/settings.py` 340–343; `execution/tasks.py` `process_market_data`, `conversation_response`

### Evidence

```10:13:backend/celery.py
app = Celery("backend")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.conf.beat_scheduler = "django_celery_beat.schedulers:DatabaseScheduler"
```

Settings set `CELERY_BROKER_POOL_LIMIT = 10` and serializers. There is no `CELERY_TASK_TIME_LIMIT`, `CELERY_TASK_SOFT_TIME_LIMIT`, `task_acks_late`, or worker concurrency other than `solo`.

`conversation_response` polls OpenAI every 0.5 s for up to 30 s on the worker thread (`execution/tasks.py` 1263–1319). `process_market_data` then calls `timer.sleep(2)`, `timer.sleep(1)`, and `timer.sleep(1)` around order creation (around 1088–1112).

### Description

`--pool=solo` means one task runs at a time. `-B` means the scheduler cannot tick while that task runs. Redis will keep accepting new messages. Nothing in this codebase bounds queue depth or sheds load.

### Complexity

- Throughput: O(1) task at a time. Latency of a queued job is the sum of every job ahead of it.
- Space: O(queue depth) in Redis.

### Trigger

Trading hours, when limit-order checks, stop-loss, take-profit, returns, chart updates, and chat tasks overlap. A few chat sessions are sufficient.

### Scaling Behavior

If chat occupies the worker 30 s and orders arrive faster than that, backlog grows by roughly `arrival_rate − 1/30` tasks per second. At 10 chat tasks/minute and 30 s each, the worker is saturated by chat alone (10 × 30 s = 300 s of work per 60 s). Limit orders and stops wait. Clients retry. The queue grows faster.

Example: producer 1,000 jobs/hour, consumer effectively 120 jobs/hour because each job sleeps or polls. Backlog ≈ 880 jobs/hour, unbounded until Redis memory or the dyno is restarted. Restarting a solo worker with a deep Redis queue replays the backlog into an already late Beat schedule.

### Failure Mode

Queue explosion, missed stops during market hours, Beat drift, retry amplification, Redis memory growth.

### Estimated Impact

Market-hours protection (`calc_stop_loss`, `calc_take_profit`, limit checks) shares the same thread as chat. A handful of concurrent AI sessions can push stop checks past the close.

### How to Verify

`celery inspect active`, Redis `LLEN` on the broker list, and task runtime histograms for `process_market_data` vs `calc_stop_loss`. Compare enqueue time to start time during a 10-user chat soak.

### Recommended Fix

Split Beat onto its own process. Use a prefork or threads pool with a small concurrency (2–4) **and** a per-task time limit (for example 60 s soft / 90 s hard on chat, 30 s on order checks). Remove the decorative `sleep` calls. Cap how many chat tasks may run at once (a Redis semaphore or a dedicated queue with `worker -Q chat,default` and a low chat concurrency).

### Trade-offs

Higher concurrency increases Postgres and Mongo connections from the worker. A hard time limit can abandon an in-flight order write; those tasks need idempotent order creation before the limit is safe. A separate chat queue means chat can be slow without blocking stops, which is the intended isolation.

---

### 4.3 Leaderboard work multiplies by clan count on a public endpoint

**Severity:** Critical  
**Confidence:** Confirmed  
**Category:** Algorithmic / Database / Cost  
**Affected Component:** `competition/models.py` `getProfit`, `get_leaderboard`, `Clan.profit_comparison`; `competition/views.py` `TopClans`; `ClanViewSet` / `ClanSerializer`

### Evidence

```291:316:competition/models.py
def getProfit(portfolio):
    positions = CompetitionPosition.objects.filter(portfolio=portfolio, status="close")
    ...
        profit = sum(
            [position.profit_loss - position.commission for position in positions]
        )
```

```304:340:competition/models.py
def get_leaderboard():
    # cached_leaderboard = cache.get('leaderboard')
    base_query = CompetitionPortfolio.objects.filter(
        competition__status="current", active=True
    )
    for account in base_query:
        profit, status = getProfit(account)
    ...
    # cache.set('leaderboard', ranked_clans, timeout=60*5)
    return ranked_clans
```

```392:396:competition/models.py
    def profit_comparison(self):
        competition = Competition.objects.filter(status="current").first()
        if competition and timezone.now() > competition.start_date:
            leaderboard = get_leaderboard()
```

```2552:2600:competition/views.py
class TopClans(APIView):
    permission_classes = (AllowAny,)
    def get(self, request):
        ...
            for account in portfolio:
                profit, status = getProfit(account)
            ...
            for data in ranked_clans:
                ...
                    data["profit_comparison"] = clan.profit_comparison
            return Response(ranked_clans[:3])
```

`ClanSerializer` includes `member`, `members_count`, and `profit_comparison`. `ClanViewSet.list` is `AllowAny` and wraps `cache_page(60 * 60 * 2)`. `retrieve` is not cached. DRF has no default `PAGE_SIZE`, so `list` builds the full clan list.

### Description

`getProfit` loads every closed position for a portfolio and sums in Python (the `commission` property on the related model is pure Python, so this is a full row fetch, not an aggregate). `TopClans` does that for every active portfolio, then `profit_comparison` does it again for every clan. The 5-minute cache around `get_leaderboard` is commented out.

`commission` is a `@property` on positions in the execution app; competition positions follow the same pattern in `getProfit` (`position.commission`). Each position row is materialized.

### Complexity

- Time: O(C × P × T) queries and Python summation.
- Space: O(T) per portfolio query, and the full clan payload including M2M members on `ClanViewSet`.
- Scaling variable: portfolios and clans. See the table in section 3.

### Trigger

`GET` of top clans while a competition is `current` and `now > start_date`. Also any clan list/retrieve that touches the serializer during that window. Cache expiry every 2 hours on `ClanViewSet.list` is a stampede: concurrent misses all run the nested scan.

### Scaling Behavior

Work grows with the **product** of clans and portfolios, not with the 3 clans returned. A client that polls every few seconds, or many anonymous clients after a cache expiry, multiplies that product by request rate.

At 50 RPS against an uncached `TopClans` with the 1,000-portfolio row in section 3: about 5 million portfolio-queries per second. Postgres connection and CPU collapse before the app’s Python loop finishes one request.

### Failure Mode

DB overload, web worker stuck, cascading timeouts, retry storm from clients.

### Estimated Impact

This is a work-amplification endpoint: response size is 3 clans; backend work is the whole competition.

### How to Verify

Django query log or Silk (already optional in local settings) on one `TopClans` call. Count queries. Repeat with 10, 100, and 1,000 portfolios in a fixture. Query count should be flat after the fix and linear-to-quadratic before it.

### Recommended Fix

One SQL aggregate for the competition:

`CompetitionPosition` filtered to `status='close'` and current portfolios, `values('portfolio_id').annotate(profit=Sum(...))`, then group by clan in SQL or in one Python pass over that aggregate.

Compute the board once per request (or once per few minutes into Redis) and pass it into the serializer. Do not call `get_leaderboard()` from a model property. Paginate clan list and drop `member` from the list serializer (id list only on retrieve). Keep a cache, and use a lock so only one request rebuilds it (single-flight).

### Trade-offs

A cached board is stale for the TTL. A single-flight lock adds a wait for callers during refresh. Removing `member` from the list payload changes the API contract for any client that reads members from the list.

---

### 4.4 Per-symbol Mongo aggregation and unbounded chart documents on the only worker

**Severity:** Critical  
**Confidence:** Confirmed for the algorithm. Collection size and Beat schedule are assumption-based.  
**Category:** I/O / Memory / CPU  
**Affected Component:** `execution/tasks.py` `retrieve_today_live`, `update_live_1m`, `update_document`

### Evidence

```1635:1660:execution/tasks.py
    pipeline = [
        {"$project": {"_id": 0, "documents": {"$objectToArray": "$$ROOT"}}},
        {"$unwind": "$documents"},
        {"$match": { ... "documents.k": symbol ... }},
        {"$replaceRoot": {"newRoot": "$documents.v"}},
    ]
    cursor = collection_merged.aggregate(pipeline)
    data = list(cursor)
```

```1694:1713:execution/tasks.py
    stocks = [stock.symbol for stock in Stock.objects.filter(active=True).order_by("symbol")]
    for symbol in stocks:
        df = retrieve_today_live(symbol, "1")
        ...
        update_document(symbol, "chartdata_5", new_data)
```

```1604:1618:execution/tasks.py
    existing_document = collection.find_one()
    if existing_document:
        for key in ["t", "o", "h", "l", "c", "v"]:
            if key in new_data:
                existing_document[key].extend(new_data[key])
        collection.update_one({"_id": id}, {"$set": existing_document})
```

`find_one()` with no filter loads an arbitrary chart document. Arrays are appended forever. The whole document is sent back with `$set`.

### Description

Each merged price document is a map of every symbol (`get_price` does `last_item[symbol]`). The pipeline converts **every** such document to an array and unwinds it, then keeps one symbol. That cannot use a normal index on symbol because the symbol is a field **name** inside the document. Work and temporary memory scale with `documents × symbols` per call, and the call is repeated per symbol.

Chart collections store one document whose arrays grow by every bar, for the lifetime of the symbol. MongoDB’s BSON limit is 16 MB. Reads and writes copy the whole history.

### Complexity

- Aggregation: time and temp space O(D × S) per symbol call, and the task does this S times → about O(S² × D) per run if every document contains every symbol.
- Chart update: time and space O(B) per symbol, B unbounded.
- Scaling variable: trading days and tick/bar count.

### Trigger

`update_live_1m` during a weekday that is not in `BANK_HOLIDAYS`. Also any later job that calls `update_document`.

### Scaling Behavior

At 150 symbols and 1,000 merged documents/day, one run touches on the order of 150 × 1,000 full documents, each expanded by `$objectToArray`. A month of unpruned merged docs multiplies that by ~20 trading days. The solo worker is occupied for the whole run, so section 4.2’s queue grows by the duration of this job.

Chart RAM per symbol is proportional to bars. Minute bars for one symbol over 250 trading days × 6.5 hours × 60 ≈ 100,000 points × 6 arrays of numbers. That is tens of megabytes per symbol and will hit 16 MB BSON first for the hottest symbols. The failure is then a write error every run, retried by Celery’s default retry policy only if the task raises and is configured to retry; a hard failure still wastes the scan.

### Failure Mode

Mongo CPU/IO saturation, worker stall, eventual document-too-large errors, OOM on the worker if many large arrays are materialized together (`list(cursor)` plus a DataFrame).

### Estimated Impact

This job is economic amplification as well: Mongo read IOPS and the worker dyno are consumed proportional to history, to append one bar.

### How to Verify

`db.merged_live_price_trdv.explain("executionStats")` on that pipeline for one symbol. Record `totalDocsExamined`, time, and bytes. `collStats` / `objectSize` on `chartdata_5` and `chartdata_1D`. Run the task once under `py-spy` and note RSS delta.

### Recommended Fix

Store one document (or one time-series bucket) per symbol per interval, with `symbol` and `datetime` as real fields and a compound index. Query `{symbol, datetime: today}` instead of unwinding the world. For charts, `$push` with `$slice` to a fixed window, or insert one bar per document / use a time-series collection. Never read-modify-write the full history in Python.

### Trade-offs

A schema change requires a backfill and reader updates (`get_price` currently indexes the latest blob by symbol key). `$slice` drops old bars from that document; keep history in an archive collection if the product needs it.

---

### 4.5 Returns jobs scan every user or portfolio and rebuild lifetime history

**Severity:** High  
**Confidence:** Confirmed for the functions. Whether Beat currently calls `returns5` / `daily_returns` / `update_latest_cumulative_returns` is assumption-based.  
**Category:** Database / CPU / Memory  
**Affected Component:** `execution/utils.py` `daily_returns7`, `daily_returns5`, `competition_daily_returns7`; `execution/tasks.py` `daily_returns`, `cumulative_returns`, `update_latest_cumulative_returns`, `competition_daily_returns`

### Evidence

`daily_returns7` (`execution/utils.py` 1101–1131) loads `DemoPortfolio.objects.all()`, then for each portfolio queries today’s closes and, if any exist, loads **all** closed positions into nine Python lists and a pandas frame.

`daily_returns5` (same file, around 760–914) nests `User.objects.all()` × portfolios and calls `TvDatafeed().get_hist` inside that loop.

`update_latest_cumulative_returns` (`execution/tasks.py` 1521–1568) loads every `DemoDailyReturns` row for each user into a DataFrame to append one cumulative row.

Several tasks use `created__date` / `closed_at__date`, which wrap the column in a date cast and will not use a plain btree on the timestamp unless a matching expression index exists. No such index is declared on these models.

### Description

The number stored is the last row of a frame built from the portfolio’s whole life. Memory per portfolio that traded today is O(all closed positions). Query count per run is at least two per portfolio even when the user did not trade, because `positions_today.exists()` is still a query.

`daily_returns` / `cumulative_returns` / `competition_daily_returns` iterate `User.objects.all()` and then positions, and call `calculate_profit_loss()`, whose `current_price` property calls `get_price` (a full Mongo document) per position (`execution/models.py` 401–410, `execution/tasks.py` 711–729).

### Complexity

- `daily_returns7`: time O(P × T), space O(T) peak per active portfolio. P = all demo portfolios, not just those that traded.
- `daily_returns5`: plus O(P) external HTTP calls.
- Cumulative updater: time and space O(U × D) with D = days of stored returns. Grows with uptime.

### Trigger

Weekday market-hours window hardcoded around 10:02–14:30 Africa/Lagos, if the task is enabled.

### Scaling Behavior

10,000 portfolios × 2 queries = 20,000 queries per run before any pandas work. A portfolio with 10,000 closed trades builds multiple full copies (lists plus DataFrame). Concurrent with the solo-worker problem, this run blocks stops and chat for its whole duration.

### Failure Mode

Worker stall, Postgres CPU, worker RSS spike, external rate limit if `daily_returns5` is the scheduled variant.

### How to Verify

Log query count and RSS around one `returns5` invocation. `EXPLAIN (ANALYZE, BUFFERS)` the `closed_at__date=today` filter.

### Recommended Fix

Maintain daily P&L incrementally when a position closes (add that close’s P&L into today’s row). Do not reload lifetime trades. Select portfolios with a single `EXISTS` query. Fetch ASI once ( `daily_returns7` already does this via `asi_history`; keep that, delete the in-loop `TvDatafeed` path from the scheduled task). Replace `__date` filters with a half-open timestamp range so an index on `(portfolio_id, status, closed_at)` can be used.

### Trade-offs

Incremental P&L must be correct when a close is edited or reversed. A backfill is required once. Deleting the old tasks is safe only after confirming Beat does not still name them.

---

### 4.6 Every limit order becomes a permanent Beat job, and a second scanner may walk the same rows

**Severity:** High  
**Confidence:** Confirmed that each limit order inserts a `PeriodicTask`. Overlap with `process_all_*` is Likely (both code paths exist; both schedules are database-driven).  
**Category:** Queue / Database / Cost  
**Affected Component:** `execution/views.py` around 472–486; `execution/tasks.py` `process_market_data` around 1196–1206; `process_all_demo_limit_order_task`; `process_all_competition_limit_order_task`

### Evidence

```472:486:execution/views.py
                schedule, created = IntervalSchedule.objects.get_or_create(
                    every=3,
                    period=IntervalSchedule.MINUTES,
                )
                task = PeriodicTask.objects.create(
                    interval=schedule,
                    name=position.alert_name,
                    task="execution.tasks.process_limit_order",
                    args=json.dumps([position.id]),
                )
```

```636:648:execution/tasks.py
def process_all_competition_limit_order_task():
    pending_positions = CompetitionPosition.objects.filter(
        portfolio__competition__status="current", status="pending"
    )
    for pending_pos in pending_positions:
        process_competition_limit_order(pending_pos.id)
```

`process_demo_limit_order` calls `get_price` per order (Mongo, full latest document).

### Description

Beat’s database scheduler loads enabled periodic tasks. N pending orders produce N task rows and N enqueues every 3 minutes. Each enqueue is a solo-worker job that reads Postgres and Mongo. `process_all_*` walks the same pending set again if it is also scheduled.

Rows are disabled on some expiry paths (`task.enabled = False`) but are not deleted. The Beat table grows with every historical order.

### Complexity

- Scheduler work: O(enabled periodic tasks) every tick.
- Market-hours Mongo reads: O(pending orders) per 3 minutes, possibly ×2.
- Table size: O(orders ever placed).

### Trigger

Normal limit-order flow. Worst case: many “week” orders left pending.

### Scaling Behavior

1,000 pending orders → about 20,000 task enqueues per market hour (1,000 × 20 ticks), each a Mongo read, on one worker. The worker’s capacity in section 4.2 is far below that, so checks fall behind the market. Stops fire late. That is a correctness problem caused by load.

### Failure Mode

Queue buildup, late fills, Beat tick slower than the 3-minute interval (missed ticks, then catch-up bursts).

### Estimated Impact

At 5,000 pending orders the Beat table and the 3-minute enqueue wave dominate the worker. Interactive chat and chart updates wait behind them.

### How to Verify

`PeriodicTask.objects.filter(task__contains="process_limit_order", enabled=True).count()` versus `DemoPosition.objects.filter(status="pending").count()`.

### Recommended Fix

One scheduled task (or one every few seconds) that loads all pending orders and one price snapshot (`get_stockdata2` is already a single document). Delete or never create per-order `PeriodicTask` rows. Index `(status)` or partial index `WHERE status='pending'`.

### Trade-offs

A single scanner has a coarser latency (the schedule interval) than a dedicated timer per order. That interval should be explicit. Deleting old Beat rows is an operational cleanup; do it in batches.

---

### 4.7 Leaderboard cache task inserts a new Beat row every run

**Severity:** High  
**Confidence:** Confirmed in code. Production enablement is assumption-based, but the function creates the schedule itself, so one manual or first run starts the growth.  
**Category:** Queue / Database  
**Affected Component:** `streaks/tasks.py` `cache_regular_leaderboard`, `cache_weekly_awards`

### Evidence

```167:220:streaks/tasks.py
    for user in User.objects.all():
        demo_trades = DemoPosition.objects.filter(...).count()
        competition_trades = CompetitionPosition.objects.filter(...).count()
        ...
    cache.set("regular_leaderboard", leaderboard_data)
    ...
    PeriodicTask.objects.create(
        interval=interval,
        name="Cache Regular Leaderboard",
        task="streaks.tasks.cache_regular_leaderboard",
        ...
    )
```

`cache.set` is called without a timeout argument. Django’s default `TIMEOUT` is 300 seconds, so the key does expire. The comment says 10 minutes; the code does not pass 600. The serious bug is `PeriodicTask.objects.create` with no `get_or_create` and no “already exists” check. `name` is unique in django-celery-beat, so the **second** run can throw `IntegrityError` after doing the full user scan — or, if names were ever made unique per run elsewhere, rows would multiply. As written, every successful first run schedules a duplicate name that fails on the next execution **after** the O(U) query loop. `cache_weekly_awards` has the same pattern (lines 241–251).

If the unique constraint is not present in the deployed Beat version, rows multiply and every copy runs the full scan.

### Complexity

- Per run: O(U) count queries (two per user). `__date` filters as in 4.5.
- Beat rows: O(1) extra attempt per run; failure mode depends on the unique index. Treat unique-name failures as confirmed waste (full scan, then exception) and row multiplication as speculative pending a schema check.

### Trigger

The task running once.

### Scaling Behavior

10,000 users → 20,000 count queries every 10 minutes, on the solo worker, before the create-task error. That is ~33 queries/second sustained from this job alone, plus Beat overhead.

### Failure Mode

Worker time stolen from trading tasks; repeated full scans; scheduler exceptions.

### How to Verify

Count `PeriodicTask` rows named `Cache Regular Leaderboard`. Log query count for one run.

### Recommended Fix

Create the periodic task once, in a migration or admin, not at the end of the task. Replace the per-user counts with two grouped queries (`values('portfolio__user').annotate(Count('id'))`). Pass an explicit cache timeout.

### Trade-offs

A grouped query is harder to read and must match the same date window. One-time schedule creation means changing the interval is an ops change, not an accidental side effect of the job.

---

### 4.8 Admin analytics and “paginate the serialized list” load whole tables

**Severity:** High  
**Confidence:** Confirmed  
**Category:** Memory / Database / latency  
**Affected Component:** `anyon/views.py` `AnalyticsView` (about 1296–1363); `AdminViewSupportMessageRequestThread` (2919–2923); similar blocks around 2823–2837 and 2978

### Evidence

```1308:1363:anyon/views.py
        users = User.objects.all()
        ...
        positions = exec_models.DemoPosition.objects.all()
        comp_positions = CompetitionPosition.objects.all()
        ...
        total_portfolio_value = round(
            sum([position.amount_invested for position in positions_close])
            + sum([position.amount_invested for position in comp_positions_close]),
            2,
        )
        ...
        transactions = models.DemoTransaction.objects.all()
        comp_transactions = CompetitionTransaction.objects.all()
```

```2919:2923:anyon/views.py
        serializer = self.serializer_class(
            messages, many=True, context={"request": request}
        )
        paginator = self.pagination_class()
        paginated_data = paginator.paginate_queryset(serializer.data, request)
```

`CustomizedPaginator.max_page_size` is 10, but the queryset is evaluated and serialized **before** pagination. Page size does not limit database or serializer work.

### Description

`AnalyticsView` pulls every position into the web process and sums in Python. Filter/count afterwards (`positions.filter(status="open")`) hits the database again, so the `.all()` materialization is pure overhead plus a second round of queries.

Support-thread admin builds the full serialized list, then slices it. Serializer cost includes nested fields and, for S3 logos elsewhere, presigns.

### Complexity

- Time and space: O(rows) per request.
- Scaling variable: users, positions, threads. Grows with uptime.

### Trigger

Staff opening analytics or support inbox. A refresh loop or several staff users makes it concurrent on the one Daphne process.

### Scaling Behavior

100,000 positions × two tables resident in RAM, plus Python lists of Decimals. On a 512 MB web dyno this is an OOM risk. Pagination of 10 rows does not change that.

### Failure Mode

Web OOM or multi-second stalls that block WebSockets on the same process (section 4.1).

### How to Verify

Log `len(connection.queries)` and RSS for `AnalyticsView`. Repeat after switching sums to `aggregate(Sum('amount_invested'))`.

### Recommended Fix

`aggregate` / `count` in SQL. Paginate the queryset (`paginator.paginate_queryset(messages, request)` then serialize the page). Add indexes that match the filters.

### Trade-offs

Aggregates must use the same status filters as the Python sums. Clients that depended on receiving a fully realized nested list before pagination will get one page; that is the intended contract of a paginated API.

---

### 4.9 Price reads pull the entire latest Mongo document, and some properties do it more than once

**Severity:** High  
**Confidence:** Confirmed for the read pattern. Request-rate amplification is Likely.  
**Category:** I/O / Network  
**Affected Component:** `portfolio/utils.py` `get_price`, `get_stockdata2`; `execution/models.py` `get_price`, `DemoPosition.current_price`; `portfolio/models.py` `Stock.ltp`, `Stock.current_price`, `Stock.change`

### Evidence

```97:103:portfolio/utils.py
def get_price(symbol):
    collection = db_merged["merged_live_price_trdv"]
    last_item = collection.find_one(sort=[("_id", -1)])
    return last_item[symbol]
```

```401:408:execution/models.py
    def current_price(self):
        print(self.stock.symbol)
        try:
            price = get_price(self.stock.symbol)
```

```143:161:portfolio/models.py
    def ltp(self):
        data = get_price(self.symbol)
        ...
    def current_price(self):
        data = get_price(self.symbol)
        ...
    def change(self):
        return round(self.ltp - self.current_price, 2)
```

`Stock.change` calls `get_price` twice. `percent_change` calls `change` and `ltp`, which can be a third fetch. `print` on every `DemoPosition.current_price` access writes to stdout on the hot path.

`get_stockdata2` correctly loads the blob once. `get_details3` uses that once, then a `ThreadPoolExecutor` to format dicts and presign logos (`portfolio/utils.py` 188–193, `portfolio/s3_utils.py` 52–74). Presign is local HMAC, not an HTTP call. The thread pool still adds overhead for CPU work that is already in memory.

`StockList` (`portfolio/views.py` 447–479) is `AllowAny` and calls `get_details3` for every active stock on every request. `MostTradedStocks` (1415–1430) runs two `Count` annotations over position tables for every stock, also `AllowAny`, then presigns the top 10.

### Description

`_id` order makes `find_one(sort=_id:-1)` an index lookup of one document, not a collection scan. The cost is the **size** of that document (every symbol, many metric fields) times how often it is fetched, plus TLS to Mongo. Doing it per position or per property multiplies bytes on the wire.

### Complexity

- One `get_stockdata2`: O(document size), constant in user count.
- Per-position `current_price`: O(positions × document size).
- `MostTradedStocks`: O(open positions) aggregation, twice, per request.

### Trigger

Any code path that touches `.current_price` in a loop (several tasks in `execution/tasks.py`). Public stock list and trending endpoints under polling.

### Scaling Behavior

If the merged document is 1 MB and a portfolio view naively calls `get_price` for 20 positions, that response moves 20 MB from Mongo. `get_stockdata2` once would move 1 MB. At 100 RPS of the naive path: 2 GB/s of Mongo reads. The stock-list path is one document per request plus N presigns; at 100 RPS that is still 100 full-document reads/s if nothing caches it. There is no application cache around `get_stockdata2`.

### Failure Mode

Mongo network saturation, TLS CPU on the web dyno, slow position endpoints.

### How to Verify

Log Mongo command time and `documentSize` for `find` sorted by `_id`. Count calls per HTTP request with a profiler. Compare a position list that uses `current_price` vs `get_holdings_positions` (the latter already takes one snapshot: `execution/views.py` 4700–4706).

### Recommended Fix

Cache the latest blob in Redis for 1–2 seconds (single-flight refresh). Use it everywhere instead of `get_price` in loops. Fix `Stock.change` to read once. Remove the `print` in `current_price`. Cache `MostTradedStocks` for a short TTL; the annotation is a global aggregate and should not run per anonymous poll.

### Trade-offs

A 1–2 s price cache means quotes are slightly stale. That is usually acceptable for a list, and dangerous if a fill uses the cached price without a fresh read. Fills should keep a direct read or a clearly documented max staleness.

---

### 4.10 DynamoDB notifications grow without a TTL and are scanned on connect

**Severity:** High  
**Confidence:** Confirmed for the write and query shape. Table size is assumption-based.  
**Category:** Cost / I/O / latency  
**Affected Component:** `notifications/utils.py`; `notifications/consumers.py` connect path

### Evidence

```16:28:notifications/utils.py
def save_and_send_notification(user_id, message):
    ...
        response = table.put_item(Item=data)
```

No TTL attribute is written. `get_notifications` queries the user partition and applies `FilterExpression is_read = False`. In DynamoDB, filter expressions are applied **after** the items are read. The function then sorts in Python and slices 30 (`notifications/utils.py` 42–56). It does not paginate with `LastEvaluatedKey`, so a user with a large partition pays for up to 1 MB of reads and can still miss older unread items.

Every trade path that calls `save_and_send_notification` adds a row. WebSocket connect calls `get_notifications` synchronously on the event loop (section 4.1).

### Complexity

- Writes: O(notifications) stored, O(uptime × events).
- Reads on connect: O(items in the user partition), capped by the 1 MB page, not by the 30 returned.

### Trigger

Long-lived active traders; reconnect storms.

### Scaling Behavior

A user with 50,000 notifications pays for a large partition read on every reconnect to show 30 items. A reconnect storm of 1,000 clients multiplies that by 1,000 at the moment the dyno is already unhealthy.

### Failure Mode

DynamoDB throttling, event-loop stalls, rising AWS bill (economic amplification).

### How to Verify

CloudWatch `ConsumedReadCapacityUnits` on connect. Item count per hot `user_id`.

### Recommended Fix

Write a TTL attribute. Query a sparse GSI of unread items, or maintain the latest 30 in Redis/Postgres. Call Dynamo from a thread, not the event loop. Paginate with a limit.

### Trade-offs

TTL deletes history the product might want for an inbox. A GSI costs extra writes. Cap-and-archive keeps a small hot set.

---

### 4.11 `simple_history` on hot models, and Wallet history registered twice

**Severity:** High  
**Confidence:** Confirmed for the double registration and for history on write-heavy models. Growth rate is assumption-based.  
**Category:** Database / storage  
**Affected Component:** `portfolio/models.py` `Wallet` lines 103–104; `HistoricalRecords()` on portfolio, execution, competition, accounts, and prop models

### Evidence

```99:104:portfolio/models.py
class Wallet(auto_prefetch.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    balance = models.DecimalField(...)
    history = HistoricalRecords()
    history = HistoricalRecords()
```

Assigning `HistoricalRecords()` twice registers two history models. Each wallet balance save inserts two history rows and updates two historical tables.

Position, portfolio, clan, and profile models also use `HistoricalRecords()`. There is no retention job in the reviewed code. Every status change on a position copies the row into a history table that only grows.

### Complexity

- Writes: ×2 on wallet updates; ×2 storage on every historical model versus the live row, accumulated over uptime.
- Space: O(updates × uptime).

### Trigger

Normal trading (balance updates, position open/close) over months.

### Scaling Behavior

If wallet updates happen on every fill and each update stores two full copies, history rows dominate table size. Autovacuum, backups, and sequential scans of history get slower. Deploy-time migrations that touch these tables get slower too.

### Failure Mode

Disk growth, slower writes, longer locks during migrations, backup cost.

### How to Verify

`\dt` sizes for `historical_*` tables. Confirm two wallet history tables exist in Postgres. Compare `n_tup_ins` on history vs live tables.

### Recommended Fix

Keep a single `HistoricalRecords()` on `Wallet`. Add a retention command (archive or delete history older than a defined window) for high-churn models, or stop tracking models that change on every tick.

### Trade-offs

Less history means a shorter audit trail. Retention must be explicit so finance/compliance still has what it needs. Dropping the duplicate history model is a migration.

---

### 4.12 No throttles, no task backpressure, Redis used for four jobs

**Severity:** High  
**Confidence:** Confirmed for missing limits. Saturation point is assumption-based.  
**Category:** Scalability / reliability under load  
**Affected Component:** `backend/settings.py` `REST_FRAMEWORK`, `CACHES`, `CHANNEL_LAYERS`, Celery broker URL

### Evidence

`REST_FRAMEWORK` has no `DEFAULT_THROTTLE_CLASSES`. Celery has no `task_annotations` rate limits and no `worker_prefetch_multiplier` override (solo prefetch is moot). Production Redis URL is the broker, the result backend, the Django cache, and the channel layer (`settings.py` 325–353).

Channels group sends include full notification payloads. WebSocket history sends the entire message list (`execution/consumers.py` 92–97). Large channel messages land in Redis.

### Description

When the database or worker is saturated, the API still accepts work. Clients retry. Chat tasks, cache misses, and channel traffic all hit one Redis.

There is no circuit breaker around Mongo or OpenAI. A slow Mongo holds request threads (or the solo worker) until the client or Heroku’s router times out (typically 30 s). The server keeps working after the client has gone.

### Complexity

Admission: unbounded. Overload cost: O(offered load), including retries.

### Trigger

Traffic spike, dependency slowdown, or the leaderboard/analytics endpoints in this report.

### Failure Mode

Retry storm, Redis memory, router timeouts with orphaned work, cascading failure (section 9).

### How to Verify

Load test with Mongo latency injected (toxiproxy or a test double). Watch in-flight requests and Redis memory. There should be a cap and a fast 429/503; today there is not.

### Recommended Fix

DRF throttles on anonymous and trading endpoints, stricter on `TopClans`, `StockList`, and chat. Separate Redis for Channels or at least a max message size. Celery `task_time_limit` and a bounded chat queue. Timeouts on Mongo client construction (the module-level `MongoClient` does not set `serverSelectionTimeoutMS` / `socketTimeoutMS` in `portfolio/utils.py` 21–23 or `execution/tasks.py` 54).

### Trade-offs

Throttles reject real users during peaks unless they are per-user and the limit matches the product. A Mongo socket timeout fails the request instead of hanging; callers must handle that.

---

### 4.13 Postgres connections kept for 10 minutes behind PgBouncer

**Severity:** Medium  
**Confidence:** Likely. `CONN_MAX_AGE=600` and `bin/start-pgbouncer-stunnel` are confirmed. Pool mode and pool size are not in the repo.  
**Category:** Database / concurrency  
**Affected Component:** `backend/settings.py` 117–123; `Procfile` web command

### Evidence

```117:123:backend/settings.py
DATABASES = {
    "default": dj_database_url.config(
        conn_max_age=600,
        default=os.environ.get("DATABASE_URL"),
    )
}
```

### Description

`CONN_MAX_AGE=600` holds Django’s connection for 10 minutes per thread. Heroku PgBouncer is often in transaction pooling mode. Persistent server connections plus transaction pooling pins server connections and is a documented Django/PgBouncer failure mode (connections not returned, or session state leaking across clients).

`database_sync_to_async` uses a thread pool. Each thread can hold one connection for 600 s. Theoretical connections ≈ web dynos × sync-DB threads + worker dynos × worker processes. With today’s Procfile that is a small number (one web process, one solo worker). It becomes dangerous if Daphne or Celery concurrency is raised without lowering `CONN_MAX_AGE` or sizing PgBouncer.

### Complexity

Connections: O(dynos × threads), held for 600 s after the query.

### Trigger

Scaling web or worker dynos; chatty sync ORM on the async loop’s thread pool.

### Failure Mode

`too many connections`, pool checkout waits, request threads blocked on checkout (which, on Daphne, stalls more work).

### How to Verify

PgBouncer `SHOW POOLS` and `SHOW CLIENTS` during load. Confirm `pool_mode`. Compare with `CONN_MAX_AGE=0`.

### Recommended Fix

If pool mode is transaction, set `CONN_MAX_AGE=0`. Size server connections as `web_dynos × threads + worker_dynos × concurrency`, under Postgres `max_connections` with headroom.

### Trade-offs

`CONN_MAX_AGE=0` adds a checkout per request through PgBouncer. That is cheaper than holding a server connection, and it is the usual pairing with transaction-mode PgBouncer.

---

### 4.14 Public mini-chart walks every Mongo history collection

**Severity:** Medium  
**Confidence:** Confirmed  
**Category:** I/O  
**Affected Component:** `portfolio/utils.py` `get_mini_data`; `portfolio/views.py` `MiniData` (`mini-chart/`)

### Evidence

```77:84:portfolio/utils.py
def get_mini_data():
    db = connect_to_mongodb("anyon_history")
    collection_names = db.list_collection_names()
    for collection_name in collection_names:
        collection = db[collection_name]
        last_27_items = list(collection.find().sort("datetime", -1).limit(27))
```

`MiniData` has no `permission_classes` override. The project default is `IsAuthenticated` (`settings.py` 191), so this is not anonymous. It is still one request → one query per collection.

`get_historical_data` (`portfolio/utils.py` 59–64) does `list(collection.find())` with no limit. It is imported in `portfolio/views.py` and not called from that file. It is a latent O(collection size) spike if a view starts calling it.

### Complexity

- Time: O(collections) round trips.
- Space: O(collections × 27).
- `get_historical_data`: O(documents in that symbol) if used.

### Trigger

Authenticated clients polling mini-chart. Missing index on `datetime` makes each `sort` a collection scan (assumption-based; indexes are not in git).

### Scaling Behavior

200 symbols → 200 finds per request. At 10 RPS, 2,000 finds/s.

### Failure Mode

Mongo saturation, slow dashboard.

### How to Verify

Count commands per request. `explain` one `find().sort(datetime:-1).limit(27)`.

### Recommended Fix

One collection with `symbol`, index `(symbol, datetime)`, and a single aggregation `$group` / `$topN`, or a precomputed trend field updated by the price job. Cache the response for tens of seconds.

### Trade-offs

Precomputation lags the last bar by the job interval. A combined aggregation is one heavy query instead of N light ones; it needs the index.

---

### 4.15 Position and portfolio queries lack declared indexes; `__date` filters block them

**Severity:** Medium  
**Confidence:** Likely. Models show almost no `db_index` or `Meta.indexes` (grep over `models.py`). Actual production indexes may have been added by hand.  
**Category:** Database  
**Affected Component:** `execution/models.py` `DemoPosition`; `competition` position models; tasks that filter `status`, `portfolio`, `closed_at__date`

### Description

Hot filters are `status="pending"|"open"|"close"`, `portfolio=...`, and a day boundary. Without a composite index, each per-portfolio loop (sections 4.3, 4.5, 4.6) is a sequential scan or a weakly selective index. `auto_prefetch` is used on foreign keys and reduces some Python-side follow-on queries; it does not create these indexes. `select_related` / `prefetch_related` appear in only a handful of modules, so several admin and list serializers still follow FKs per row.

### Complexity

Each query: O(table) if unindexed, O(log n + matches) if indexed. Multiplied by the loops above.

### How to Verify

`EXPLAIN (ANALYZE, BUFFERS)` for pending-order scan, today’s closes, and `getProfit`’s filter. `pg_stat_user_indexes` for unused sequential scans.

### Recommended Fix

Partial indexes, for example:

- `DemoPosition (portfolio_id, closed_at) WHERE status = 'close'`
- `DemoPosition (status) WHERE status = 'pending'`
- the same for competition positions

Rewrite `__date` lookups to range comparisons so the planner can use them.

### Trade-offs

Indexes slow writes slightly and cost disk. Partial indexes match the hot subset and stay smaller.

---

### 4.16 OpenAI calls have no concurrency cap beyond the solo worker

**Severity:** Medium  
**Confidence:** Confirmed  
**Category:** Cost / latency  
**Affected Component:** `portfolio/utils.py` `get_alert_data`; `execution/tasks.py` `conversation_response`, `process_market_data`

### Description

Each chat message can call the Chat Completions or Assistants API and poll until 30 s. Tool handlers call `get_price` (full Mongo document) per tool call. There is no per-user rate limit in this code. Token usage grows with thread history because the Assistants thread is reused (`thread_id` is passed through). That history is unbounded in this repository’s control flow.

### Complexity

- Occupancy: up to 30 s per message on the only worker (section 4.2).
- Tokens: O(thread length × turns). Data-dependent.
- Cost: O(messages × tokens).

### Trigger

Users or bots sending trading prompts.

### Failure Mode

Worker starvation and a token bill proportional to message rate. A stuck run burns the full 30 s poll (about 60 HTTP GETs at 0.5 s).

### How to Verify

Log OpenAI latency and token usage per task. Count in-flight `process_market_data` tasks.

### Recommended Fix

Per-user rate limit, a dedicated queue, and a hard timeout that cancels the run. Cap thread history sent to the model.

### Trade-offs

Rate limits change the chat UX. Cancelling a run can leave an order unplaced; the task should be idempotent on order id.

---

### 4.17 Synchronous Lambda invoke inside a Celery task

**Severity:** Medium  
**Confidence:** Confirmed for the call. Schedule is assumption-based.  
**Category:** Latency / queue  
**Affected Component:** `execution/tasks.py` `update_live_1m_lambda` around 1718–1746

### Evidence

`lambda_client.invoke(..., InvocationType="RequestResponse", ...)` sends **all** active symbols in one payload and waits for the function. The solo worker is blocked for the whole Lambda duration. No client read timeout is set in the snippet.

### Complexity

O(Lambda duration) worker stall per run. Payload size O(symbols).

### Failure Mode

Worker stall if Lambda is slow or retries internally. Duplicate work if both `update_live_1m` and `update_live_1m_lambda` are scheduled.

### Recommended Fix

`Event` invocation, or a short boto read timeout, and only one of the two updaters scheduled.

### Trade-offs

Async invoke means the worker does not see Lambda errors unless a callback or DLQ is added.

---

### 4.18 `get_details3` thread pool and stdout logging on hot paths

**Severity:** Low  
**Confidence:** Confirmed  
**Category:** CPU  
**Affected Component:** `portfolio/utils.py` `get_details3`; `print` in `current_price` and many tasks

### Description

`ThreadPoolExecutor()` defaults to `min(32, cpu+4)` threads to build dicts from data already in memory and to HMAC-presign logos. Threads do not make presign faster in proportion, and they increase context switches on a small dyno. `print` of symbols and dataframes in returns jobs is synchronous stdout, which on Heroku is log drain I/O.

### Complexity

O(stocks) per list request, with a thread-startup tax.

### Recommended Fix

Presign in a plain loop or cache signed URLs until near expiry (expiry is 24 h in settings). Drop prints in loops.

### Trade-offs

Cached signed URLs must be invalidated if the object key changes. Log volume drops, which also drops debug detail.

---

### 4.19 Duplicate `order_by` and full user scans in admin list endpoints

**Severity:** Low  
**Confidence:** Confirmed  
**Category:** Database  
**Affected Component:** `portfolio/views.py` `MostTradedStocks` (two identical `order_by("-num_positions")`); `anyon/views.py` and `competition/views.py` `User.objects.all()` / `objects.all()` list endpoints that do paginate some of the time

### Description

The double `order_by` is redundant. Several admin views call `.all()` and rely on a paginator only after the queryset exists; where `paginate_queryset` is applied to the queryset (for example activity logs around `anyon/views.py` 2887), the database can limit rows. Those are fine. The ones that serialize first are covered in 4.8.

### Recommended Fix

Remove the duplicate `order_by`. Audit remaining `.all()` handlers and paginate the queryset.

---

### 4.20 Module-level Mongo clients and `tlsAllowInvalidCertificates`

**Severity:** Low for performance, noted because of connection behavior  
**Confidence:** Confirmed  
**Category:** Other (connection setup)  
**Affected Component:** `portfolio/utils.py` 21–23; `execution/tasks.py` 54

### Description

A process-wide `MongoClient` is appropriate (pooling). It is created at import with certificate verification disabled and without explicit pool or timeout settings. Default pool size is 100. One web dyno and one worker will not open 100 each unless concurrency rises. Slow or black-holed Mongo then waits on driver defaults (tens of seconds) while holding the solo worker or a request.

### Recommended Fix

Set `serverSelectionTimeoutMS`, `socketTimeoutMS`, and `maxPoolSize` to match dyno concurrency. Turn certificate verification on.

### Trade-offs

Short timeouts fail fast during a Mongo blip. Callers must handle errors. Valid TLS may require the proper CA bundle in the image.

---

## 5. Memory Leak & Growth Analysis

No classic “append to a global list on every request and never drop it” leak was confirmed in the web process. Growth that **is** in the code is mostly unbounded storage and per-request spikes.

| Allocation / Resource | Lifetime | Growth Driver | Bounded? | Cleanup Exists? | Risk |
|---|---|---|---|---|---|
| Mongo chart arrays (`t,o,h,l,c,v`) | Process-independent document | Every bar appended | No | No trim / `$slice` | Spike + hard 16 MB failure. Confirmed. |
| `merged_live_price_trdv` documents | Collection | Inserts from price collectors (outside this request path, visible in `tradingView-API/`) | No, in the writers reviewed | Not in `update_live_1m` | Aggregation cost grows with uptime. Likely. |
| `django_celery_beat_periodictask` | Database | One row per limit order; leaderboard task inserts more | No | `enabled=False` on some cancels, not delete | Scheduler load. Confirmed writes. |
| `simple_history` tables | Database | Every save of tracked models; wallet ×2 | No | No retention job | Disk. Confirmed. |
| DynamoDB notifications | Table | Every `save_and_send_notification` | No | No TTL | Read cost on connect. Confirmed. |
| Celery result keys in Redis | Redis | Every task result | Default 1 day expiry (Celery default; not overridden here) | Default expiry | Bounded by 1 day unless large return values. Likely. |
| Django cache keys | Redis | Leaderboard, `cache_page` | Yes (default 300 s or `cache_page` TTL) | TTL | Stampede, not a leak. |
| WebSocket `get_messages` list | Request/connection | Conversation length | No | Connection close drops it | Spike per connect. Confirmed. |
| `AnalyticsView` position lists | Request | All positions | No | End of request | Spike / OOM. Confirmed. |
| `daily_returns7` DataFrames | Task | Closed positions of one portfolio | No cap | End of iteration | Spike on the worker. Confirmed. |
| `ThreadPoolExecutor` in `get_details3` | Request | Active stocks | Pool default | Context manager exits | Churn, not a leak. |
| Channels groups | Redis | Connected sockets | Per connection | `group_discard` on disconnect | Leak if disconnect does not run (crash). Speculative. |

**Confirmed leaks:** none of the “process RSS grows forever because a Python global retains requests” type, from static review.

**Suspected leaks:** Channels group membership if the process dies between `group_add` and `group_discard` (Redis group entries). Needs a soak with kill -9.

**Legitimate but dangerous growth:** history tables, chart documents, Beat rows, DynamoDB items.

**Temporary spikes:** analytics, returns DataFrames, `$objectToArray` aggregation, full conversation history on connect.

---

## 6. Database Analysis

### Likely N+1 or per-row query loops

| Site | Queries per trigger | Main cost |
|---|---|---|
| `get_leaderboard` / `TopClans` | 1 + (portfolios) + (clans × portfolios) | Round trips and row I/O |
| `cache_regular_leaderboard` | 2 × users | Round trips |
| `daily_returns7` | ≥ 2 × portfolios, more when a close exists | Round trips + Python RAM |
| `ClanSerializer.member` | M2M load per clan | Payload and queries |
| `Clan.members_count` | `COUNT` on M2M per clan | Round trips |
| `DemoPosition.current_price` | 1 Mongo `find_one` per access | Network bytes |
| Admin `.all()` then Python `sum` | Full table read | Memory and I/O |

`select_related` / `prefetch_related` are rare (a handful of call sites in the whole repo). `auto_prefetch` on models helps some FK access and does not fix the explicit per-user loops.

### Index candidates

Confirm with `EXPLAIN` before adding:

- `DemoPosition (status)` partial `pending` and `open`
- `DemoPosition (portfolio_id, status, closed_at)`
- `CompetitionPosition` equivalents
- `DemoDailyReturns (user_id, created)` and `(portfolio_id, created)`
- `CompetitionPortfolio (competition_id, active)`
- Beat table is Django’s; the fix is fewer rows, not a new index

`__date` lookups should become range predicates or they will not use those indexes.

### Query amplification

One `TopClans` request: see section 3. Order-of-magnitude **10²–10⁶** queries depending on competition size.

One returns run: **O(portfolios)** queries.

One limit-order wave: **O(pending)** Mongo reads every 3 minutes.

### Connection pool

`CONN_MAX_AGE=600`. No `OPTIONS` for `MAX_CONNS`. PgBouncer is on the web dyno only (`Procfile`); the worker uses `DATABASE_URL` directly unless the worker env also points at PgBouncer (not visible here).

Theoretical, if web is scaled without changing code:

`web_dynos × sync_threads_holding_conns + worker_dynos × 1 (solo)`

Numbers are unknown until dyno formation and the asgiref thread-pool size are measured. Today’s Procfile implies a small ceiling and a sharp one: the database is more likely to be overloaded by **query count** than by connection count until concurrency is raised.

### Transactions

No long explicit `transaction.atomic` blocks were identified as the main risk. `simple_history` adds an insert to the same transaction as the model save, widening each write. Wallet’s double history widens it again.

### Pagination

`portfolio` and `prop` paginators cap `page_size` at 100. `anyon` `CustomizedPaginator` caps at 10. Several admin views paginate **after** `serializer.data`, so the cap does not apply to the query (section 4.8). `ClanViewSet` list is unpaginated.

### Large result sets

`AnalyticsView`, `get_historical_data` (unused from views), chart `find_one` of the whole history, WebSocket history, clan list with members.

---

## 7. Concurrency Analysis

| Topic | Assessment |
|---|---|
| Event-loop blocking | Confirmed. `time.sleep` and sync DynamoDB/ORM in async consumers. |
| Worker parallelism | Confirmed absent (`solo`). |
| Accidentally serialized work | Confirmed. Chat, stops, charts, and returns share one thread. |
| Unsafe unlimited parallelism | `get_details3` and OpenAI tool handling use unbounded default thread pools, but only for a small in-memory fan-out. Not the main risk. |
| Lock contention | No application-level locks around leaderboard rebuild. Cache stampede is the analogue. |
| Deadlock | No explicit lock-order cycle found. Database deadlocks are possible if history + balance updates contend, but not demonstrated. |
| Connection starvation | Likely only after scale-out. See 4.13. |
| Task explosion | Confirmed enqueues from per-order Beat rows. Leaderboard task re-creates itself. |
| Priority inversion | Confirmed in effect: a 30 s chat task delays stop-loss with no priority queue. |

Increasing Celery concurrency without indexes, time limits, and `CONN_MAX_AGE` changes will increase Postgres and Mongo load and can reduce throughput (section 4.2 and 4.13).

---

## 8. Resource Explosion Scenarios

### A. Public leaderboard poll

```
1 request
  → P portfolio queries
  → C × P queries inside profit_comparison
Example P=1,000, C=100 → ~101,000 queries
× 20 polls/minute from a few clients
  → ~2,000,000 queries/minute
```

Postgres CPU and connections go first. Daphne stays busy and WebSockets stall.

### B. Limit-order fan-out during market hours

```
N pending orders
  → N Beat jobs / 3 minutes
  → N Mongo full-document reads
  → plus process_all_* if enabled (another N)
N = 2,000 over a 5-hour session
  → 2,000 × 100 ticks = 200,000 worker jobs
Solo worker at even 50 ms each = 10,000 s ≈ 2.8 h of backlog per 5 h of market
```

Stops and chat share that backlog.

### C. Chat retry storm

```
1 message → up to 30 s worker hold + ~60 OpenAI status GETs
Client timeout 30 s → retry
3 client retries × 30 s = 90 s of duplicate work per logical message
10 users retrying → worker busy for 15 minutes of serial work
```

### D. Chart job

```
S symbols × D merged documents × (unwind all symbols)
S=150, D=5,000 → 750,000 document expansions in one task
Worker RSS: one DataFrame of today’s points per symbol, serially
Chart rewrite: O(all historical bars) bytes written per symbol per run
```

### E. Reconnect storm

```
1,000 sockets connect
  → 1,000 DynamoDB partition reads
  → 1,000 full chat histories
  → each subsequent message time.sleep(1) on one loop
```

### F. Scale-out feedback

```
High latency → more web dynos
  → more CONN_MAX_AGE connections
  → Postgres connection errors
  → higher latency → more dynos
```

This is not active at solo/single-daphne, and it becomes the next failure mode if sections 4.1–4.2 are “fixed” only by adding processes.

---

## 9. Cascading Failure Chains

**Chain 1 — leaderboard**

Uncached `TopClans` → thousands of Postgres queries → query latency climbs → Daphne request threads/loop stay busy → WebSocket heartbeats miss → clients reconnect → notification connects scan DynamoDB and call `time.sleep` on the next message → dyno is saturated → router timeouts → clients retry `TopClans`.

**Chain 2 — worker**

Chart aggregation or chat poll holds the solo worker → Beat cannot enqueue on time, then enqueues a catch-up burst → limit-order and stop tasks start late → fills happen in a burst of writes (`simple_history` included) → Postgres write latency climbs → web trade requests slow → users retry orders → more Beat rows and more tasks.

**Chain 3 — Mongo slowdown**

`get_price` has no short socket timeout → each position price waits the driver default → web requests pile up on the one loop → health checks fail → platform restarts the dyno → cold process reconnects Postgres (`CONN_MAX_AGE`) and Mongo → in-flight Celery task is redelivered → duplicate work on an already slow Mongo.

**Chain 4 — cache expiry**

`ClanViewSet` `cache_page` TTL hits → many clients miss at once → each miss runs section 4.3 → same as chain 1. The 2-hour TTL synchronizes the herd.

**Chain 5 — Redis**

Channel history payloads and Celery results share Redis with the broker → Redis memory or latency climbs → both HTTP fan-out (channels) and task delivery slow → workers and web stall together. There is no second broker.

---

## 10. Recommended Load Tests

Production RPS is unknown. Treat “1×” as the current weekday peak once it is measured (Heroku router logs). Until then, use the absolute levels below.

| Test | Dataset | Concurrency | Duration | Expected observation |
|---|---:|---:|---:|---|
| Baseline `GET` health or a cheap authenticated read | n/a | 1, 10, 50 | 5 min | p50/p95/p99, RSS flat |
| `TopClans` during a fake “current” competition | 100 / 1,000 / 10,000 portfolios, 10–50 closed trades | 1, then 10, then 50 | 10 min | Query count ≈ C×P before fix; ~O(1) aggregates after. p99 and Postgres CPU. |
| `ClanViewSet` list, cold cache and just after TTL | 50 and 500 clans | 1 and 50 | 10 min | Stampede: concurrent misses should be 1 rebuild after single-flight |
| `StockList` and `MostTradedStocks` | 200 stocks, 100k open positions | 10, 50, 100 | 10 min | Mongo bytes and Postgres aggregate time |
| WebSocket chat | 10 messages/connection | 1, 20, 100 connections | 10 min | Event-loop lag. Unrelated HTTP p99 should stay flat after sleep removal |
| Limit-order wave | 100, 1,000, 5,000 pending | Beat at 3 min, or one scanner | 30 min | Queue depth, age of oldest task, Mongo reads |
| `returns5` / `daily_returns7` | 1k and 10k portfolios, 100 closes each on 10% of them | 1 (it is batch) | 1 run | Duration, peak RSS, query count |
| `update_live_1m` | 50 and 200 symbols, 1k and 10k merged docs | 1 | 1 run | `docsExamined`, duration, RSS |
| Analytics admin | 10k, 100k, 1M positions | 1 and 5 | 5 min | RSS, whether the dyno OOM-kills |
| 2× and 5× peak HTTP | production-shaped mix | 2×, 5× | 15 min | Which resource saturates first (loop, Postgres, Mongo, Redis) |
| Burst | 0 → 5× for 60 s | spike | 60 s | Queue and p99 recovery time |
| Dependency slowdown | Mongo +200 ms, OpenAI hanging | 10 | 10 min | Timeouts fire; worker stays available for stops |
| Cold cache | flush Redis cache | 50 on clan list and stock list | 5 min | Stampede size |

Capture for each: p50/p95/p99/max, RPS, CPU, RSS, Mongo `docsExamined`, Postgres queries/request, connections, queue depth, oldest task age, error rate, timeout rate.

Success bar for the leaderboard fix: query count stays under a small constant (single-digit aggregates) at 10,000 portfolios. Success bar for the worker split: stop-loss lag p99 stays under the schedule interval while chat runs at 10 concurrent sessions.

---

## 11. Soak Test Plan

Run 24 hours, then 7 days on a staging copy with synthetic trading.

Steady load: 20 authenticated users polling stock list every 5 s, 5 WebSockets sending one message a minute, 100 pending limit orders, Beat enabled, a competition of 1,000 portfolios.

Track every 1 minute:

- Web and worker RSS and CPU
- Python heap / GC (tracemalloc or `memray` for a shorter window)
- Open file descriptors (`/proc/self/fd`)
- Postgres connections and `pg_stat_activity` state
- Mongo connections and slow-query count
- Redis memory, key count, list length of the Celery queue
- Beat row count (`PeriodicTask`)
- DynamoDB item count for a test user
- Chart document `objectSize` for one symbol
- `historical_*` table size
- HTTP p50/p95/p99
- Age of oldest Celery message
- Event-loop lag

A positive slope in RSS **after** the first hour, under constant RPS, is a leak. A positive slope in Beat rows, chart `objectSize`, history tables, or Dynamo items is unbounded growth even if RSS is flat. Both are failures. Queue age must oscillate around the schedule interval, not climb through the day.

---

## 12. Performance Guardrails

| Guardrail | Suggestion grounded in this code |
|---|---|
| Pagination | Paginate querysets before serialization. Default and max page size on every list, including clans. |
| Leaderboard | Single-flight cache; never recompute per clan. |
| Request rate | DRF throttle on anonymous and on `TopClans`, `StockList`, `MostTradedStocks`, chat. |
| Celery | Time limits. Separate Beat process. Queue for chat vs trading safety (stops, limits). |
| Beat rows | One scanner for pending orders. No `PeriodicTask.objects.create` inside the task body. |
| Mongo | Socket and server-selection timeouts. Max document size alert on chart collections. |
| Postgres | `CONN_MAX_AGE=0` if PgBouncer is transaction-mode. Statement timeout on the app role. |
| DynamoDB | TTL. Max items returned. |
| WebSocket | Auth before accept. Max message size. Max messages/minute/connection. History cap. No `time.sleep` on the loop. |
| Payloads | Cap conversation history sent to OpenAI. |
| History tables | Retention. |
| Cache | Explicit TTLs. Single-flight on expiry. Do not cache pages that embed per-object quadratic work without fixing the work. |
| Process counts | If web dynos or worker concurrency increase, re-budget Postgres connections first. |
| Body size | Django’s default upload limits are fine; do not raise them without a streaming path. |

---

## 13. Performance Regression CI

Keep these in CI with fixtures, not production traffic.

| Check | Fail if |
|---|---|
| `TopClans` or `get_leaderboard` query count on a 100-portfolio fixture | Count grows with clan count (should be ≤ a fixed aggregate budget, e.g. 10 queries) |
| `daily_returns7` on 100 portfolios × 20 trades | Query count or peak RSS regresses > 15% |
| Pending-order scanner | Enqueues more than 1 task per scan (guards against per-order Beat rows returning) |
| `get_price` call count while rendering 20 positions | More than 1 Mongo find |
| Import/smoke | `time.sleep` added under `async def` in `consumers.py` (simple grep gate) |
| Serializer page | Support-thread test: queryset evaluated row count equals page size, not table size |

Do not put the 7-day soak or 5× load test in every CI run. Run those nightly or before a scale change.

---

## 14. Optimization Priority

### Immediate

1. Remove event-loop blocking (`time.sleep`, sync DynamoDB/ORM) and accept-before-auth on WebSockets.  
2. Stop per-clan `get_leaderboard()` and ship one aggregate plus a single-flight cache. `TopClans` is unauthenticated and quadratic.  
3. Get trading-safety tasks off the chat/chart critical section: separate Beat, time limits, one pending-order scanner, delete per-order periodic tasks.  
4. Stop the per-symbol `$objectToArray` scan and the unbounded chart read-modify-write before a symbol hits 16 MB.

These four can take the API down or freeze fills without a traffic spike much larger than a single competition plus a few chat users.

### Before scaling further

5. Incremental daily returns; delete in-loop `TvDatafeed` and `User.objects.all()` jobs.  
6. Fix leaderboard Beat self-insert and the per-user count loop.  
7. SQL aggregates for admin analytics; paginate querysets before serializers.  
8. Short-TTL cache around the latest price document; fix double `get_price` on `Stock`.  
9. DynamoDB TTL and a bounded unread query.  
10. Decide `CONN_MAX_AGE` against real PgBouncer `pool_mode` before adding dynos.  
11. Wallet double `HistoricalRecords` and a history retention policy.  
12. Throttles and Mongo timeouts.

### Optimization opportunities

13. Replace `get_mini_data`’s per-collection finds with one indexed query and a short cache.  
14. Drop hot-path `print` and the `get_details3` thread pool.  
15. Index confirmation via `EXPLAIN` (section 4.15).  
16. Dedicated Redis for Channels if broker latency moves with WebSocket traffic.  
17. `get_historical_data` full-collection read: leave it unused or cap it before wiring it to a view.

Correctness notes: price caching and incremental P&L must not change fill prices silently. Single-flight caching can serve a slightly stale leaderboard. Time limits on order tasks require idempotent creates so a killed task does not double-open a position. Removing `member` from clan list responses is an API change.

---

## Measurements still required

These are not in the repository. They confirm or reject the assumption-based parts:

1. Heroku formation: web dyno count and size, worker dyno count, router timeout.  
2. PgBouncer `pool_mode`, `default_pool_size`, `max_client_conn`.  
3. Enabled `PeriodicTask` rows (names, intervals, last run).  
4. `merged_live_price_trdv` document count and average size; largest `chartdata_*` document.  
5. Row counts: users, demo portfolios, open/pending/closed positions, clans, `historical_*` sizes.  
6. `EXPLAIN (ANALYZE)` for `TopClans`’s position filter and the pending-order filter.  
7. A weekday trace: Celery queue depth, task runtime by name, Daphne event-loop lag, Mongo bytes out, Postgres queries/second.
