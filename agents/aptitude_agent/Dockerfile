# DigiDARA Aptitude Trainer Agent (Flask)
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

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request,json; req=urllib.request.Request('http://127.0.0.1:5000/api/invoke', data=json.dumps({'action':'health'}).encode(), headers={'Content-Type':'application/json'}); urllib.request.urlopen(req, timeout=3).read()" || exit 1

CMD ["gunicorn", "-w", "4", "--timeout", "240", "-b", "0.0.0.0:5000", "app:app"]
