"""Self-registration with the DigiDARA orchestrator (Strategy F).

Sync-requests + daemon-heartbeat-thread pattern, since Flask has no async
lifespan hook — copy-adapted from
agents/codeforge_agent/services/lms-api/integration/registry_client.py,
the reference Flask-flavored implementation named in STRATEGY_F.md. This
app always runs via `waitress.serve(...)` in run.py, never a dev-server
reloader, so there is no double-import/double-registration risk to guard
against beyond the `_started` flag below.
"""

import atexit
import hashlib
import hmac
import json
import logging
import os
import threading
import time
import uuid
from pathlib import Path

import requests

logger = logging.getLogger("job_agent.integration.registry_client")

AGENT_ROOT = Path(__file__).resolve().parents[1]
MANIFEST = json.loads((AGENT_ROOT / "manifest.json").read_text(encoding="utf-8"))

ORCHESTRATOR_URL = os.environ.get("ORCHESTRATOR_URL", "http://127.0.0.1:8100").rstrip("/")
AGENT_PUBLIC_URL = os.environ.get("AGENT_PUBLIC_URL")
HEARTBEAT_INTERVAL_SECONDS = int(os.environ.get("HEARTBEAT_INTERVAL_SECONDS", "30"))
REQUEST_TIMEOUT_SECONDS = 10

# Must match the orchestrator's own AGENT_SHARED_SECRET (app/auth/service_auth.py)
# and its dev-mode default — every agent's registry_client.py shares this same
# fallback so local dev works with no .env changes.
AGENT_SHARED_SECRET = os.environ.get("AGENT_SHARED_SECRET", "dev-only-agent-shared-secret")


def _sign_request(method: str, path: str, body: bytes) -> dict:
    timestamp = str(int(time.time()))
    request_id = uuid.uuid4().hex
    body_hash = hashlib.sha256(body).hexdigest()
    canonical = "\n".join((timestamp, request_id, method.upper(), path, body_hash))
    signature = hmac.new(AGENT_SHARED_SECRET.encode(), canonical.encode(), hashlib.sha256).hexdigest()
    return {"X-Agent-Timestamp": timestamp, "X-Agent-Request-Id": request_id, "X-Agent-Signature": signature}


_stop_event = threading.Event()
_heartbeat_thread = None
_started = False


def _endpoint():
    if AGENT_PUBLIC_URL:
        return AGENT_PUBLIC_URL
    return f"http://{MANIFEST['host']}:{MANIFEST['port']}{MANIFEST.get('path', '/api/invoke')}"


def _registration_payload():
    return {
        "agent_name": MANIFEST["agent_name"],
        "version": MANIFEST["version"],
        "endpoint": _endpoint(),
        "description": MANIFEST["description"],
        "input_schema": MANIFEST["input_schema"],
        "output_schema": MANIFEST.get("output_schema", {}),
        "owner": MANIFEST.get("owner"),
        "plan_tier": MANIFEST.get("plan_tier", "free"),
    }


def _register():
    body = json.dumps(_registration_payload()).encode("utf-8")
    headers = {"Content-Type": "application/json", **_sign_request("POST", "/registry/register", body)}
    try:
        response = requests.post(
            f"{ORCHESTRATOR_URL}/registry/register",
            data=body,
            headers=headers,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        # A non-2xx here (401 from a mismatched AGENT_SHARED_SECRET is the
        # common one) used to pass silently — requests only raises on
        # network-level failures, not HTTP error statuses — which made a
        # completely unregistered agent look like it had started cleanly.
        response.raise_for_status()
        logger.info("job_agent registered with orchestrator at %s", ORCHESTRATOR_URL)
    except requests.RequestException:
        logger.warning("job_agent registration failed; will retry on next heartbeat", exc_info=True)


def _heartbeat():
    # Includes `endpoint` (not just agent_name/version) so a long-lived
    # process whose AGENT_PUBLIC_URL was corrected after it last started
    # self-heals on the next heartbeat instead of staying registered under a
    # stale endpoint until manually restarted -- register() only runs once
    # at boot, so this was the only thing keeping a live process's
    # registered endpoint in sync with its actual current config.
    body = json.dumps({"agent_name": MANIFEST["agent_name"], "version": MANIFEST["version"], "endpoint": _endpoint()}).encode("utf-8")
    headers = {"Content-Type": "application/json", **_sign_request("POST", "/registry/heartbeat", body)}
    try:
        response = requests.post(
            f"{ORCHESTRATOR_URL}/registry/heartbeat",
            data=body,
            headers=headers,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        if response.status_code == 404:
            _register()
    except requests.RequestException:
        logger.warning("job_agent heartbeat failed", exc_info=True)


def _heartbeat_loop():
    while not _stop_event.wait(HEARTBEAT_INTERVAL_SECONDS):
        _heartbeat()


def start():
    """Register once and start the background heartbeat loop. Idempotent."""
    global _heartbeat_thread, _started
    if _started:
        return
    _started = True
    _register()
    _heartbeat_thread = threading.Thread(target=_heartbeat_loop, daemon=True)
    _heartbeat_thread.start()


def stop():
    """Stop the heartbeat loop and best-effort deregister. Safe to call twice."""
    global _started
    if not _started:
        return
    _started = False
    _stop_event.set()
    try:
        headers = _sign_request("DELETE", "/registry/deregister", b"")
        requests.delete(
            f"{ORCHESTRATOR_URL}/registry/deregister",
            params={"agent_name": MANIFEST["agent_name"], "version": MANIFEST["version"]},
            headers=headers,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.RequestException:
        pass


atexit.register(stop)
