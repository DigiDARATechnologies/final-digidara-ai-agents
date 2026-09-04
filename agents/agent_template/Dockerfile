# DigiDARA agent template (FastAPI via agent_wrapper.py) — copy this
# Dockerfile as-is into any new agent folder cloned from this template.
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd --create-home --uid 1000 --shell /usr/sbin/nologin appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8201

# agent_template exposes GET /health (via agent_wrapper.py), not the
# POST /api/invoke {"action": "health"} convention used by the real agents
# in this repo — its manifest.json has no "path" field either. Confirm
# which convention your copied agent actually follows before reusing this
# HEALTHCHECK verbatim.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8201/health', timeout=3).read()" || exit 1

CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "-w", "4", "-b", "0.0.0.0:8201", "main:app"]
