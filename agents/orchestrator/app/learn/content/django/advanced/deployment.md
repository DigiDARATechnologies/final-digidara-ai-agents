---
title: Deploying Django to production
summary: Prepare settings, serve with Gunicorn behind Nginx, handle static files, run migrations safely and containerise with Docker.
takeaways:
- Never use runserver in production: use Gunicorn (or Uvicorn) behind Nginx
- Split settings by environment and read secrets from environment variables
- Static files, migrations and health checks are part of every release
---
## What changes in production

| Development | Production |
| --- | --- |
| `runserver` | **Gunicorn** behind **Nginx** |
| `DEBUG = True` | `DEBUG = False` |
| SQLite file | PostgreSQL or MySQL |
| files served by Django | static files served by Nginx or a CDN |
| secrets in `settings.py` | secrets in the environment |
| `print()` | structured logging and error tracking |

## Settings from the environment

```python
import os

def env(name, default=None, required=False):
    value = os.environ.get(name, default)
    if required and value is None:
        raise RuntimeError(f"Set the {name} environment variable")
    return value

os.environ["DJANGO_DEBUG"] = "0"
os.environ["DJANGO_ALLOWED_HOSTS"] = "skilldara.example.com,www.skilldara.example.com"

DEBUG = env("DJANGO_DEBUG", "0") == "1"
ALLOWED_HOSTS = [h for h in env("DJANGO_ALLOWED_HOSTS", "").split(",") if h]
print(DEBUG, ALLOWED_HOSTS)

try:
    env("DJANGO_SECRET_KEY", required=True)
except RuntimeError as error:
    print(error)
```

```output
False ['skilldara.example.com', 'www.skilldara.example.com']
Set the DJANGO_SECRET_KEY environment variable
```

Failing fast with a clear message when a required secret is missing is better than starting with an unsafe default. Libraries such as **django-environ** make this tidier:

```py
import environ
env = environ.Env()
DATABASES = {"default": env.db("DATABASE_URL")}          # DATABASE_URL=postgres://user:pass@host/dbname
```

## Database and static files

```py
DATABASES = {"default": {
    "ENGINE": "django.db.backends.postgresql",
    "NAME": env("DB_NAME"), "USER": env("DB_USER"), "PASSWORD": env("DB_PASSWORD"),
    "HOST": env("DB_HOST"), "PORT": "5432",
    "CONN_MAX_AGE": 60,                       # reuse connections for a minute
}}

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"        # collectstatic copies every app's static files here
MEDIA_URL = "/media/"                         # user uploads
MEDIA_ROOT = BASE_DIR / "media"
```

```py
python manage.py collectstatic --noinput
```

Nginx (or a CDN) serves `STATIC_ROOT` directly. For a simple single-server setup, **WhiteNoise** lets Django serve its own static files efficiently.

## Gunicorn and Nginx

```py
pip install gunicorn
gunicorn config.wsgi:application --workers 4 --bind 127.0.0.1:8000 --timeout 60
```

```py
server {
    listen 443 ssl;
    server_name skilldara.example.com;

    location /static/ { alias /srv/app/staticfiles/; expires 30d; }
    location /media/  { alias /srv/app/media/; }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Because Nginx terminates HTTPS, tell Django to trust the forwarded header: `SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")`. For async or WebSocket apps, run the ASGI app with `uvicorn config.asgi:application` or Gunicorn's Uvicorn worker.

## Docker

```py
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN python manage.py collectstatic --noinput
RUN useradd --create-home appuser
USER appuser
EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "--workers", "4", "--bind", "0.0.0.0:8000"]
```

Copy `requirements.txt` first so Docker caches the install step, run as a **non-root user**, and pass secrets in at run time, never inside the image.

## Release checklist

| Step | Done when |
| --- | --- |
| `python manage.py check --deploy` | no warnings you cannot justify |
| settings read secrets from the environment | `DEBUG` off, strong `SECRET_KEY` |
| `python manage.py migrate` | run during the release, after taking a backup |
| `python manage.py collectstatic` | static files are served by Nginx or a CDN |
| HTTPS with a valid certificate | and the secure-cookie settings on |
| a `/health/` endpoint | monitored, and used by the load balancer |
| logging and error alerts | Sentry or similar |
| backups | tested by actually restoring one |
| dependencies pinned | `requirements.txt` with exact versions |

## Safe migrations on a live site

1. Add new columns as **nullable** (or with a default) so old code still works.
2. Deploy the code that uses them.
3. Backfill data, then tighten constraints in a later release.
4. Remove old columns only after no running code reads them.

Doing it in small steps means the site never breaks halfway through a deploy.

:::interview
**Interviewers often ask:** "How do you deploy a Django app?" Run it with Gunicorn behind Nginx (HTTPS, static files), keep settings and secrets in the environment with `DEBUG` off, use PostgreSQL, run `collectstatic` and `migrate` on release, containerise with Docker, and add health checks, logging and backups.
:::
