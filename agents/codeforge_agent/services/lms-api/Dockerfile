# DigiDARA CodeForge Agent (Flask, lms_api app factory)
FROM python:3.12-slim

WORKDIR /app

# Pick up Debian security patches for OS packages already present in the
# base image (e.g. gzip, libpcre2, libsqlite3, perl-base CVEs) that aren't
# refreshed just by pulling a floating python:3.12-slim tag.
RUN apt-get update \
    && apt-get upgrade -y \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd --create-home --uid 1000 --shell /usr/sbin/nologin appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 4000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request,json; req=urllib.request.Request('http://127.0.0.1:4000/api/invoke', data=json.dumps({'action':'health'}).encode(), headers={'Content-Type':'application/json'}); urllib.request.urlopen(req, timeout=3).read()" || exit 1

# scripts/migrate.py and scripts/seed.py only ever ran in CI tests -- nothing
# applied migrations or catalog content in any real deployment. The 100
# existing Python problems must have been loaded by someone running seed.py
# by hand once; new catalog content (e.g. the first MySQL problems) silently
# never reached production because of this gap. Both scripts are idempotent
# (schema_migrations tracking; INSERT ... ON DUPLICATE KEY UPDATE), so it's
# safe to run them on every boot, same pattern as aptitude_agent's
# "flask db upgrade".
CMD ["sh", "-c", "python scripts/migrate.py up && python scripts/seed.py && exec gunicorn -w 4 -b 0.0.0.0:4000 'lms_api:create_app()'"]
