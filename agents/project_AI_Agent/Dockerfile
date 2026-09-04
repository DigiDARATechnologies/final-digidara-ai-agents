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
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd --create-home --uid 1000 --shell /usr/sbin/nologin appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request,json; req=urllib.request.Request('http://127.0.0.1:8000/api/invoke', data=json.dumps({'action':'health'}).encode(), headers={'Content-Type':'application/json'}); urllib.request.urlopen(req, timeout=3).read()" || exit 1

CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "-w", "4", "-b", "0.0.0.0:8000", "app.api.main:app"]
