---
title: Deploying Flask to production
summary: Run Flask with Gunicorn behind Nginx, containerise it with Docker, and add health checks, logging and safe configuration.
takeaways:
- Never use flask run in production; use a WSGI server such as Gunicorn
- Put Nginx in front for HTTPS, static files and buffering
- Docker makes the app run the same everywhere
---
## What changes in production

| Development | Production |
| --- | --- |
| `flask run --debug` | **Gunicorn** (a production WSGI server) |
| one process | several worker processes |
| plain HTTP | **HTTPS** through Nginx or a load balancer |
| SQLite file | a managed database (PostgreSQL, MySQL) |
| secrets in code | secrets in the environment |
| print statements | structured logs |

## WSGI and Gunicorn

**WSGI** is the standard way a Python web app talks to a web server. Flask is a WSGI app. **Gunicorn** is a WSGI server that runs several copies (workers) of your app to handle many requests at once.

Create a `wsgi.py`:

```py
from app import create_app
app = create_app("production")
```

Run it:

```py
pip install gunicorn
gunicorn --workers 4 --bind 0.0.0.0:8000 --timeout 60 wsgi:app
```

A common starting point for the number of workers is `2 × CPU cores + 1`. On Windows use **Waitress** instead (`waitress-serve --port=8000 wsgi:app`), because Gunicorn needs Linux or macOS.

## Nginx in front

Nginx handles the internet-facing work: HTTPS, slow clients, static files, and passing real requests to Gunicorn.

```py
server {
    listen 443 ssl;
    server_name api.example.com;

    ssl_certificate     /etc/letsencrypt/live/api.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.example.com/privkey.pem;

    location /static/ {
        alias /srv/app/static/;
        expires 30d;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Because Flask now sits behind a proxy, tell it to trust the forwarded headers, or it will think every request comes from Nginx over HTTP:

```py
from werkzeug.middleware.proxy_fix import ProxyFix
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
```

## Docker

```py
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN useradd --create-home appuser
USER appuser
EXPOSE 8000
HEALTHCHECK CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"
CMD ["gunicorn", "--workers", "4", "--bind", "0.0.0.0:8000", "wsgi:app"]
```

Notes: copy `requirements.txt` first so Docker caches the install step, run as a **non-root user**, and keep secrets out of the image (pass them as environment variables at run time).

## A health check

Load balancers and Docker need a cheap URL that says "I am alive and can reach my database":

```python
from flask import Flask, jsonify

app = Flask(__name__)
database_ok = True       # in a real app: try a trivial query like SELECT 1

@app.get("/health")
def health():
    if not database_ok:
        return jsonify(status="unhealthy"), 503
    return jsonify(status="ok")

client = app.test_client()
print(client.get("/health").status_code, client.get("/health").get_json())
database_ok = False
print(client.get("/health").status_code, client.get("/health").get_json())
```

```output
200 {'status': 'ok'}
503 {'status': 'unhealthy'}
```

A **503** tells the load balancer to stop sending traffic to this copy.

## Logging

```python
import json
import logging
import sys

class JsonFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps({"level": record.levelname, "message": record.getMessage(), "logger": record.name})

handler = logging.StreamHandler(sys.stdout)      # containers usually log to standard output
handler.setFormatter(JsonFormatter())
log = logging.getLogger("skilldara")
log.addHandler(handler)
log.setLevel(logging.INFO)
log.propagate = False
log.info("payment received")
log.warning("slow query")
```

```output
{"level": "INFO", "message": "payment received", "logger": "skilldara"}
{"level": "WARNING", "message": "slow query", "logger": "skilldara"}
```

Logs written as JSON can be searched by tools such as Loki, CloudWatch or the ELK stack.

## A release checklist

| Item | Done when |
| --- | --- |
| `DEBUG = False`, strong `SECRET_KEY` from the environment | yes |
| HTTPS with a valid certificate | yes |
| database migrations run (`flask db upgrade`) | yes |
| static files served by Nginx or a CDN | yes |
| a `/health` endpoint, monitored | yes |
| logs and error alerts (Sentry or similar) | yes |
| backups, tested by restoring one | yes |
| dependencies pinned in `requirements.txt` | yes |

:::interview
**Interviewers often ask:** "How do you deploy a Flask app?" Run it with Gunicorn (several workers) behind Nginx for HTTPS and static files, package it in Docker, keep configuration and secrets in the environment, run migrations on release, and add health checks, logging and monitoring.
:::
