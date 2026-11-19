---
title: What is Django?
summary: Django is a batteries-included Python web framework. See what comes in the box, how a request flows, and when to choose it.
takeaways:
- Django includes the ORM, admin, authentication, forms, templates and security tools out of the box
- It follows the MVT pattern: Model, View, Template
- A request travels URL → view → (model, template) → response
---
## The framework with the batteries included

Flask gives you a small core and lets you pick the rest. **Django** takes the opposite approach: almost everything a typical web app needs is already inside.

| Need | Django already has |
| --- | --- |
| Database access | the **ORM** (models and queries in Python) |
| Changing the database safely | **migrations** |
| An admin panel to manage data | the **admin site**, generated from your models |
| Login, passwords, permissions | `django.contrib.auth` |
| Forms and validation | the **forms** system |
| HTML pages | the **template** language |
| Security | CSRF, XSS, SQL-injection and clickjacking protection by default |
| Caching, sessions, email, i18n | built in |

This is why Django is a popular choice for content sites, dashboards, e-commerce and school or college portals: you spend your time on your features, not on wiring.

## MVT: Model, View, Template

| Part | Job | Lives in |
| --- | --- | --- |
| **Model** | describes your data and talks to the database | `models.py` |
| **View** | receives a request, decides what to do, returns a response | `views.py` |
| **Template** | the HTML with placeholders | `templates/` |
| **URL configuration** | maps a URL to a view | `urls.py` |

The life of one request:

1. The browser asks for `/courses/python/`.
2. Django matches the URL in `urls.py` and picks a view function.
3. The view asks a **model** for data (the database).
4. The view passes the data to a **template**, which makes HTML.
5. The view returns the HTML as a response.

## A view in six lines

```python
from django.http import HttpResponse
from django.urls import path
from django.test import Client

def home(request):
    return HttpResponse("Hello from Django!")

urlpatterns = [path("", home, name="home")]

response = Client().get("/")
print(response.status_code)
print(response.content.decode())
```

```output
200
Hello from Django!
```

:::note
The runnable examples in this course use a **pre-configured** Django: an in-memory database and one app called `demo`. In your own project, `settings.py` and `manage.py` (next lesson) do this set-up. `Client()` is Django's test client: it sends requests to your project without starting a server.
:::

## Django or Flask?

| | Django | Flask |
| --- | --- | --- |
| Philosophy | batteries included, one standard way | small core, you choose |
| Admin and auth | built in | add extensions |
| Project structure | fixed and familiar | up to you |
| Best for | full products with data, users and an admin | small services, custom APIs, learning |
| Learning curve | more to learn at first | quick start |

Neither is "better". Teams that need an admin panel and user accounts by Monday usually pick Django.

## What this course covers

| Part | You will learn |
| --- | --- |
| Basics | project layout, URLs, views, templates |
| Data | models, migrations, the ORM, relationships, query optimisation |
| Features | the admin, forms, authentication and permissions, class-based views |
| APIs | Django REST Framework |
| Advanced | middleware, signals, testing, security, caching, background jobs, deployment |
