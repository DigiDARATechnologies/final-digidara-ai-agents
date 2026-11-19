---
title: Caching and background jobs
summary: Speed up Django with the cache framework, per-view caching and database optimisation, and move slow work to Celery.
takeaways:
- Cache expensive results with cache.get_or_set; use Redis in production
- Measure first; most slowness is queries (N+1, missing indexes, no pagination)
- Slow work such as email and reports belongs in a Celery task
---
## Measure first

Do not guess. In development, use **django-debug-toolbar** to see the SQL and timing of each page. The usual causes, in order: too many queries (N+1), missing indexes, loading far too many rows, and repeating the same expensive work.

## The cache framework

```python
from django.core.cache import cache

cache.clear()
cache.set("greeting", "hello", timeout=60)
print(cache.get("greeting"), cache.get("missing"), cache.get("missing", "default"))

calls = []

def expensive_leaderboard():
    calls.append(1)
    return ["Asha", "Meena"]

first = cache.get_or_set("leaderboard", expensive_leaderboard, timeout=300)
second = cache.get_or_set("leaderboard", expensive_leaderboard, timeout=300)
print(first, second, "real computations:", len(calls))

cache.delete("leaderboard")
cache.get_or_set("leaderboard", expensive_leaderboard, timeout=300)
print("after deleting the key:", len(calls))
```

```output
hello None default
['Asha', 'Meena'] ['Asha', 'Meena'] real computations: 1
after deleting the key: 2
```

The first call computed and stored the result; the second came straight from the cache. Deleting the key forced a fresh computation.

## Choosing a backend

```py
# development: in-memory, per process (the default)
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

# production: Redis, shared by all server processes
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": "redis://127.0.0.1:6379/1",
    }
}
```

`LocMemCache` is separate in every worker process, so in production with several Gunicorn workers use **Redis** (or Memcached).

## Cache a whole view

```python
from django.http import JsonResponse
from django.test import Client
from django.urls import path
from django.views.decorators.cache import cache_page

hits = []

@cache_page(60)
def report(request):
    hits.append(1)
    return JsonResponse({"generated": len(hits)})

urlpatterns = [path("report/", report)]
cache.clear()
client = Client()
print(client.get("/report/").json(), client.get("/report/").json(), "view ran:", len(hits), "time")
```

```output
{'generated': 1} {'generated': 1} view ran: 1 time
```

The second request never reached the view. For pages that differ per user, add `vary_on_cookie` or cache only the expensive fragment, never a page that shows private data to everyone.

:::warning
The hard part of caching is **invalidation**: knowing when the stored answer is stale. Use short timeouts for changing data, delete keys when the data changes (a signal or the save method), and never cache per-user data under a shared key.
:::

## Database indexes

```python
from django.db import models, connection

class Enrolment(models.Model):
    email = models.EmailField(db_index=True)             # an index for fast lookups
    course = models.CharField(max_length=30)

    class Meta:
        indexes = [models.Index(fields=["course", "email"], name="course_email_idx")]

with connection.schema_editor(collect_sql=True) as editor:
    editor.create_model(Enrolment)
print([line for line in editor.collected_sql if "INDEX" in line])
```

```output
['CREATE INDEX "demo_enrolment_email_eb0508ce" ON "demo_enrolment" ("email");', 'CREATE INDEX "course_email_idx" ON "demo_enrolment" ("course", "email");']
```

Add indexes to columns you filter, sort or join on often. Without one, the database must scan every row.

## Background jobs with Celery

Sending email, building a PDF or calling a slow API should not make the user wait. **Celery** runs such work in a separate **worker** process, fed by a queue (Redis or RabbitMQ).

```py
# config/celery.py
import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
app = Celery("config")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
```

```py
# courses/tasks.py
from celery import shared_task
from django.core.mail import send_mail

@shared_task(bind=True, max_retries=3)
def send_welcome_email(self, user_id):
    user = User.objects.get(pk=user_id)
    try:
        send_mail("Welcome!", "Glad you joined.", None, [user.email])
    except ConnectionError as error:
        raise self.retry(exc=error, countdown=30)        # try again in 30 seconds
```

```py
# in a view or a signal
from django.db import transaction

def signup(request):
    user = create_user(request.POST)
    transaction.on_commit(lambda: send_welcome_email.delay(user.id))      # queue it AFTER the row is saved
    return redirect("welcome")
```

```py
celery -A config worker --loglevel=info          # start a worker
celery -A config beat                            # start the scheduler for periodic tasks
```

| Habit | Why |
| --- | --- |
| pass **ids**, not objects | the task loads fresh data; objects cannot be sent safely |
| use `transaction.on_commit` | the worker could run before the row exists |
| make tasks **idempotent** | running one twice must not cause harm (no double email or charge) |
| set retries and timeouts | networks fail |
| for a nightly job use **Celery beat** or cron | scheduled work |

For simple needs, newer options such as **Django 6's built-in tasks** or **django-q2** can replace a full Celery set-up. The principle is the same: do slow work outside the request.

:::interview
**Interviewers often ask:** "How would you speed up a slow Django page?" Measure first (debug toolbar). Fix N+1 queries with `select_related` and `prefetch_related`, add indexes, paginate, cache expensive results (Redis), and move slow tasks to Celery.
:::
