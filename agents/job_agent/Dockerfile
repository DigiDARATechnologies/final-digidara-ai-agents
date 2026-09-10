# DigiDARA Job Agent (Flask API and ingestion worker)
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt /app/job_agent/requirements.txt
RUN pip install --no-cache-dir -r /app/job_agent/requirements.txt

COPY . /app/job_agent

RUN useradd --create-home --uid 1000 --shell /usr/sbin/nologin appuser \
    && mkdir -p /app/job_agent/uploads \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 5020

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5020/health', timeout=3).read()" || exit 1

# Batch collection is queued for job-worker and returns immediately. A
# 90-second ceiling still gives one-source validation/import endpoints room
# for bounded provider retries without allowing wedged HTTP workers to live
# for five minutes.
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5020", "--timeout", "90", "job_agent.app:create_app()"]
