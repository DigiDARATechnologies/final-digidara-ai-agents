# DigiDARA Capstone Project Agent (FastAPI)
FROM python:3.12-slim

WORKDIR /app

# tesseract-ocr is required by app/ocr/extractor.py (pytesseract). Playwright
# (app/execution/browser_check.py) is intentionally NOT installed here: that
# module already treats a missing Playwright install as "no execution
# evidence" rather than a failure (see its own docstring), so skipping the
# heavy `playwright install --with-deps chromium` step keeps this image
# lean without changing behavior. Add it later if that evidence path is
# needed in this deployment.
# Changing SECURITY_UPDATES rebuilds the step below, so `apt-get upgrade`
# fetches current Debian security fixes instead of reusing a cached layer
# (CI passes today's date; bump the default to refresh the servers' images).
ARG SECURITY_UPDATES=2026-10-14
RUN echo "security updates: ${SECURITY_UPDATES}" \
    && apt-get update \
    && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# /app/uploads must exist in the image so the capstone_uploads volume
# (docker-compose.yml) starts out owned by appuser, not root.
RUN useradd --create-home --uid 1000 --shell /usr/sbin/nologin appuser \
    && mkdir -p /app/uploads \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request,json; req=urllib.request.Request('http://127.0.0.1:8000/api/invoke', data=json.dumps({'action':'health'}).encode(), headers={'Content-Type':'application/json'}); urllib.request.urlopen(req, timeout=3).read()" || exit 1

CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "-w", "4", "--timeout", "300", "-b", "0.0.0.0:8000", "app.api.main:app"]
