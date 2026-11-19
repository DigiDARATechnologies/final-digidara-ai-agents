---
title: Project and apps
summary: Create a Django project, understand every file it generates, and learn how projects are split into apps.
takeaways:
- django-admin startproject creates the project; startapp creates a reusable feature module
- settings.py controls the whole project; INSTALLED_APPS lists the active apps
- One project holds many apps, such as accounts, courses and payments
---
## Set up

```py
python -m venv .venv
.venv\Scripts\activate            # macOS and Linux: source .venv/bin/activate
pip install django
django-admin startproject config .
python manage.py runserver
```

Open http://127.0.0.1:8000: the Django rocket page means it works. The dot at the end of `startproject config .` creates the project in the current folder instead of an extra nested one.

## What was generated

```py
manage.py              # the command-line tool: runserver, migrate, startapp, test ...
config/
  __init__.py
  settings.py          # ALL configuration lives here
  urls.py              # the root URL map
  asgi.py              # entry point for async servers
  wsgi.py              # entry point for Gunicorn and similar servers
```

| File | You use it to |
| --- | --- |
| `manage.py` | run every Django command for this project |
| `settings.py` | set the database, installed apps, middleware, templates, static files, secrets |
| `urls.py` | list the URL patterns for the whole site |
| `wsgi.py` / `asgi.py` | tell a production server how to start your project |

## Projects and apps

A **project** is the whole website. An **app** is one feature of it, kept in its own folder so it can be understood and reused on its own.

```py
python manage.py startapp courses
python manage.py startapp accounts
```

```py
courses/
  __init__.py
  admin.py        # register models in the admin site
  apps.py         # the app's configuration
  models.py       # database tables
  views.py        # request handlers
  tests.py        # tests
  migrations/     # database change history
```

A good split is by **feature**: `accounts`, `courses`, `payments`, `blog`. If two parts could be sold or reused separately, they are different apps.

## Register the app

Django only uses apps that are listed in `INSTALLED_APPS`:

```py
# config/settings.py
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "courses",            # your app
]
```

## Key settings

| Setting | Meaning |
| --- | --- |
| `DEBUG` | `True` shows detailed error pages (development only) |
| `SECRET_KEY` | signs sessions and tokens: keep it secret |
| `ALLOWED_HOSTS` | the domain names the site may serve (required when `DEBUG` is off) |
| `DATABASES` | which database to use (SQLite by default) |
| `INSTALLED_APPS` | active apps |
| `MIDDLEWARE` | code that wraps every request |
| `TEMPLATES` | where templates live |
| `STATIC_URL` | URL prefix for CSS, JavaScript and images |
| `TIME_ZONE`, `USE_TZ` | time handling: keep `USE_TZ = True` |

:::warning
The generated `settings.py` has the `SECRET_KEY` and `DEBUG = True` written in it. That is fine for learning, but before sharing the code or going live, read these from **environment variables** and set `DEBUG = False`. The deployment lesson shows how.
:::

## The commands you will use every day

| Command | What it does |
| --- | --- |
| `python manage.py runserver` | start the development server (reloads on save) |
| `python manage.py makemigrations` | write migration files for model changes |
| `python manage.py migrate` | apply migrations to the database |
| `python manage.py createsuperuser` | make an admin account |
| `python manage.py shell` | a Python prompt with Django loaded |
| `python manage.py test` | run the tests |
| `python manage.py collectstatic` | gather static files for production |

:::tip
Run `python manage.py migrate` right after creating a project, even before you write a model. Django's own apps (admin, auth, sessions) need their tables.
:::
