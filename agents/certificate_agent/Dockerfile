# DigiDARA AI Certification Agent (FastAPI)
FROM python:3.12-slim

WORKDIR /app

# Pick up Debian security patches for OS packages already present in the
# base image (e.g. gzip, libpcre2, libsqlite3, perl-base CVEs) that aren't
# refreshed just by pulling a floating python:3.12-slim tag.
#
# fonts-dejavu-core / fonts-liberation: python:3.12-slim ships with NO
# TrueType fonts at all. certificate_generator.py renders every certificate
# field with PIL/Pillow using real .ttf files at fixed pixel sizes; without
# these packages every font lookup silently falls back to PIL's built-in
# bitmap default font, which ignores the requested size entirely and
# renders all text at ~11px regardless of the 30-80px sizes the layout was
# designed for (the tiny/misaligned certificate text bug).
RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends fonts-dejavu-core fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd --create-home --uid 1000 --shell /usr/sbin/nologin appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8008

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request,json; req=urllib.request.Request('http://127.0.0.1:8008/api/invoke', data=json.dumps({'action':'health'}).encode(), headers={'Content-Type':'application/json'}); urllib.request.urlopen(req, timeout=3).read()" || exit 1

CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "-w", "4", "-b", "0.0.0.0:8008", "cert_app.main:app"]
