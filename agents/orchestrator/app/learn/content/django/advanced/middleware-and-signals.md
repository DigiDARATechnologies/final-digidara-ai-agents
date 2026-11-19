---
title: Middleware and signals
summary: Run code around every request with middleware, react to model events with signals, and know when each is the right tool.
takeaways:
- Middleware wraps every request and response, in order, like layers of an onion
- Signals let one part of the app react to events in another without importing it
- Both are powerful: keep them small, and prefer explicit code where you can
---
## Middleware: layers around your views

Middleware is code that runs for **every** request: before the view on the way in, and after it on the way out. Django ships with some (sessions, authentication, CSRF, security headers), and you can add your own.

```python
from django.http import JsonResponse
from django.test import Client, override_settings
from django.urls import path

calls = []

class TimingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response            # the next layer (or the view)

    def __call__(self, request):
        calls.append("timing: before")
        response = self.get_response(request)       # everything inside runs here
        response["X-Handled-By"] = "timing-middleware"
        calls.append("timing: after")
        return response

class BlockBotsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        calls.append("bots: before")
        if "badbot" in request.headers.get("User-Agent", "").lower():
            return JsonResponse({"error": "blocked"}, status=403)       # stop here: the view never runs
        return self.get_response(request)

def hello(request):
    calls.append("view")
    return JsonResponse({"hello": "world"})

urlpatterns = [path("hello/", hello)]

settings_for_demo = override_settings(MIDDLEWARE=["demo.models.TimingMiddleware", "demo.models.BlockBotsMiddleware"])
with settings_for_demo:
    client = Client()
    response = client.get("/hello/")
    print(response.status_code, response["X-Handled-By"])
    print(calls)
    calls.clear()
    blocked = client.get("/hello/", HTTP_USER_AGENT="BadBot/1.0")
    print(blocked.status_code, calls)
```

```output
200 timing-middleware
['timing: before', 'bots: before', 'view', 'timing: after']
403 ['timing: before', 'bots: before', 'timing: after']
```

The order in the `MIDDLEWARE` list matters: requests pass **down** the list and responses come back **up**. For the blocked request, `BlockBotsMiddleware` returned early, so the view never ran, yet the timing layer outside it still added its header on the way back.

| Common middleware jobs | Example |
| --- | --- |
| add headers to every response | security headers, a request id |
| log or time requests | slow-request logging |
| block or redirect early | maintenance mode, IP blocks |
| attach data to the request | the current tenant, the language |

:::tip
Middleware runs on **every** request, including static files and health checks. Keep it fast, and do the cheap check first.
:::

## Signals: react to events

A **signal** announces that something happened (a model was saved, a user logged in). Other code can **listen** and react, without the sender knowing who is listening.

```python
from django.db import models, connection
from django.db.models.signals import post_save
from django.dispatch import receiver

class Order(models.Model):
    item = models.CharField(max_length=40)
    paid = models.BooleanField(default=False)

with connection.schema_editor() as editor:
    editor.create_model(Order)

notifications = []

@receiver(post_save, sender=Order)
def announce_order(sender, instance, created, **kwargs):
    if created:
        notifications.append(f"new order for {instance.item}")
    elif instance.paid:
        notifications.append(f"order for {instance.item} was paid")

order = Order.objects.create(item="Python course")
order.paid = True
order.save()
print(notifications)
```

```output
['new order for Python course', 'order for Python course was paid']
```

Common built-in signals: `pre_save`, `post_save`, `pre_delete`, `post_delete`, `m2m_changed`, and `user_logged_in`. Your own code can define custom signals too.

In a real project, register receivers in the app's `ready()` so they are connected once:

```py
# courses/apps.py
class CoursesConfig(AppConfig):
    name = "courses"

    def ready(self):
        from . import signals          # noqa: connects the receivers
```

## When not to use a signal

Signals hide the flow: reading `order.save()` gives no hint that an email is sent somewhere else. They are also **skipped by bulk operations** (`bulk_create`, `update()`).

```python
before = len(notifications)
Order.objects.bulk_create([Order(item="Book")])
print("signals fired by bulk_create:", len(notifications) - before)
```

```output
signals fired by bulk_create: 0
```

| Use a signal for | Prefer explicit code for |
| --- | --- |
| decoupled reactions from another app (audit logs, cache clearing) | your own app's core business rules |
| hooking into third-party models you cannot edit | anything that must always happen (it can be skipped by bulk operations) |

If creating an order must always send an email, call a service function from the view. Do not rely on a signal.

:::interview
**Interviewers often ask:** "What are Django signals and what is the downside?" Signals let code react to events such as `post_save` without coupling to the sender. The downside is hidden control flow, harder debugging and testing, and that bulk operations do not trigger them.
:::
