# DigiDARA Orchestrator (FastAPI registry + gateway)
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

EXPOSE 8100

HEALTHCHECK --interval=10s --timeout=5s --start-period=60s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8100/health', timeout=3).read()" || exit 1

# --forwarded-allow-ips: take the client address from X-Forwarded-For, which
# the frontend nginx overwrites with the real visitor IP (see nginx.conf).
# Without it every request looks like it comes from the nginx container, so
# the per-IP login/signup rate limits were one bucket shared by all users.
# Safe to trust any hop: this port is never published to the host, so only
# containers on the Compose network can reach it.
CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "-w", "4", "-b", "0.0.0.0:8100", "--forwarded-allow-ips", "*", "app.main:app"]
