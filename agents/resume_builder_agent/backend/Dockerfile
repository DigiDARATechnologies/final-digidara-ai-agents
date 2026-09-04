# DigiDARA Resume Builder Agent (Flask)
FROM python:3.12-slim

WORKDIR /app

# tesseract-ocr + poppler-utils are required by app/services/import_review.py
# (pytesseract OCR and pdf2image, which shells out to poppler's pdftoppm).
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr poppler-utils \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd --create-home --uid 1000 --shell /usr/sbin/nologin appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 5010

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request,json; req=urllib.request.Request('http://127.0.0.1:5010/api/invoke', data=json.dumps({'action':'health'}).encode(), headers={'Content-Type':'application/json'}); urllib.request.urlopen(req, timeout=3).read()" || exit 1

CMD ["gunicorn", "--preload", "-w", "4", "-b", "0.0.0.0:5010", "run:app"]
