---
title: Performance, caching and background jobs
summary: Make an app fast with caching, indexes and pagination, and move slow work out of the request with a task queue.
takeaways:
- Measure first; most slowness is database queries
- Caching trades a little freshness for a lot of speed
- Work that takes seconds (email, reports) belongs in a background job
---
## Measure before you tune

Do not guess where time goes. Look at the **slow query log**, add timing in an `after_request` hook, or use a profiler. The usual suspects, in order:

1. Too many queries (the N+1 problem).
2. A missing **index** on a column you filter or join on.
3. Returning far too much data (no pagination).
4. Repeating the same expensive work for every request.
5. Slow work done **inside** the request.

## Caching

If many requests need the same result, calculate it once and **remember** it.

```python
import time
from functools import wraps

def cached(seconds):
    def decorator(fn):
        store = {}
        @wraps(fn)
        def wrapper(*args):
            now = time.monotonic()
            if args in store and now - store[args][0] < seconds:
                wrapper.hits += 1
                return store[args][1]
            wrapper.misses += 1
            value = fn(*args)
            store[args] = (now, value)
            return value
        wrapper.hits = wrapper.misses = 0
        return wrapper
    return decorator

@cached(seconds=60)
def top_students(department):
    time.sleep(0.05)                 # pretend this is an expensive database query
    return [f"{department}-topper"]

for _ in range(3):
    top_students("CSE")
top_students("ECE")
print("hits:", top_students.hits, " misses:", top_students.misses)
```

```output
hits: 2  misses: 2
```

Three calls for CSE cost one real calculation and two cache hits. For real apps use **Flask-Caching**, which can store results in memory or in **Redis** (shared between all your server processes):

```py
pip install flask-caching
```

```py
from flask_caching import Cache
cache = Cache(app, config={"CACHE_TYPE": "RedisCache", "CACHE_REDIS_URL": "redis://localhost:6379/0"})

@app.get("/leaderboard")
@cache.cached(timeout=60)          # the same response for 60 seconds
def leaderboard():
    return compute_leaderboard()
```

:::warning
The hard part of caching is **invalidation**: knowing when the stored answer is stale. Use short times for fast-changing data, delete the key when the data changes, and never cache anything that is **different for each user** under one shared key.
:::

## Database indexes

```python
import sqlite3

db = sqlite3.connect(":memory:")
db.execute("CREATE TABLE students (id INTEGER PRIMARY KEY, email TEXT, marks INTEGER)")
db.executemany("INSERT INTO students (email, marks) VALUES (?, ?)", [(f"s{i}@x.com", i % 100) for i in range(5000)])

def plan(sql):
    return db.execute("EXPLAIN QUERY PLAN " + sql).fetchone()[3]

print(plan("SELECT * FROM students WHERE email = 's42@x.com'"))
db.execute("CREATE INDEX idx_students_email ON students(email)")
print(plan("SELECT * FROM students WHERE email = 's42@x.com'"))
```

```output
SCAN TABLE students
SEARCH TABLE students USING INDEX idx_students_email (email=?)
```

Before the index the database had to **scan** every row. After it, it **searches** the index. On a table of millions of rows that is the difference between seconds and milliseconds.

## Background jobs

Some work is too slow to do while the user waits: sending email, making a PDF, calling a slow API. Do it **after** the response, in a separate worker process, using a task queue:

| Tool | Notes |
| --- | --- |
| **Celery** | the most popular; very capable; needs a broker (Redis or RabbitMQ) |
| **RQ** (Redis Queue) | simple and small, good to start |
| **APScheduler** or cron | jobs on a **schedule** (a nightly report) |

```py
# tasks.py (Celery)
from celery import Celery
celery = Celery("app", broker="redis://localhost:6379/0")

@celery.task(bind=True, max_retries=3)
def send_welcome_email(self, user_id):
    try:
        deliver(user_id)
    except TimeoutError as error:
        raise self.retry(exc=error, countdown=30)       # try again in 30 seconds
```

```py
# a view
@app.post("/signup")
def signup():
    user = create_user(request.get_json())
    send_welcome_email.delay(user.id)       # queued: returns immediately
    return {"id": user.id}, 201             # the user does not wait for the email
```

Pass **ids**, not whole objects, to a job (the job loads fresh data), and make jobs **idempotent**: running one twice must not cause harm (no double charge, no second email).

## Other quick wins

| Idea | Effect |
| --- | --- |
| compress responses (gzip) | smaller downloads |
| `Cache-Control` and `ETag` headers | the browser reuses static files |
| serve static files from Nginx or a CDN | Flask is not the fastest at files |
| connection pooling | reuse database connections |
| select only the columns you need | less data moved |

:::interview
**Interviewers often ask:** "How would you speed up a slow Flask endpoint?" Measure first. Fix N+1 queries, add indexes, paginate, cache repeated results (Redis), and move slow work to a background queue such as Celery.
:::
