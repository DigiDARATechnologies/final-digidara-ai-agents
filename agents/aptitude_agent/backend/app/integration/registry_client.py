"""Self-register the Flask Aptitude service with the DigiDARA orchestrator."""
from __future__ import annotations

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

logger = logging.getLogger("aptitude.integration.registry")
AGENT_ROOT = Path(__file__).resolve().parents[3]
MANIFEST = json.loads((AGENT_ROOT / "manifest.json").read_text(encoding="utf-8"))
ORCHESTRATOR_URL = os.environ.get("ORCHESTRATOR_URL", "http://127.0.0.1:8100").rstrip("/")
AGENT_PUBLIC_URL = os.environ.get("AGENT_PUBLIC_URL")
HEARTBEAT_INTERVAL_SECONDS = int(os.environ.get("HEARTBEAT_INTERVAL_SECONDS", "30"))
REQUEST_TIMEOUT_SECONDS = 10
_stop = threading.Event()
_thread: threading.Thread | None = None
_started = False

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


def _endpoint() -> str:
    return AGENT_PUBLIC_URL or f"http://{MANIFEST['host']}:{MANIFEST['port']}{MANIFEST.get('path', '/api/invoke')}"


def _payload() -> dict:
    return {"agent_name": MANIFEST["agent_name"], "version": MANIFEST["version"], "endpoint": _endpoint(),
            "description": MANIFEST["description"], "input_schema": MANIFEST["input_schema"],
            "output_schema": MANIFEST.get("output_schema", {}), "owner": MANIFEST.get("owner"),
            "plan_tier": MANIFEST.get("plan_tier", "free")}


def _register() -> None:
    body = json.dumps(_payload()).encode("utf-8")
    headers = {"Content-Type": "application/json", **_sign_request("POST", "/registry/register", body)}
    try:
        response = requests.post(f"{ORCHESTRATOR_URL}/registry/register", data=body, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
        logger.info("registered %s", MANIFEST["agent_name"])
    except requests.RequestException:
        logger.warning("Aptitude registry registration failed", exc_info=True)


def _heartbeat() -> None:
    # Includes `endpoint` so a long-lived process whose AGENT_PUBLIC_URL was
    # corrected after it last started self-heals on the next heartbeat
    # instead of staying registered under a stale endpoint indefinitely --
    # register() only runs once at boot.
    body = json.dumps({"agent_name": MANIFEST["agent_name"], "version": MANIFEST["version"], "endpoint": _endpoint()}).encode("utf-8")
    headers = {"Content-Type": "application/json", **_sign_request("POST", "/registry/heartbeat", body)}
    try:
        response = requests.post(f"{ORCHESTRATOR_URL}/registry/heartbeat",
                                 data=body, headers=headers,
                                 timeout=REQUEST_TIMEOUT_SECONDS)
        if response.status_code == 404:
            _register()
    except requests.RequestException:
        logger.warning("Aptitude registry heartbeat failed", exc_info=True)


def _loop() -> None:
    while not _stop.wait(HEARTBEAT_INTERVAL_SECONDS):
        _heartbeat()


def start() -> None:
    global _started, _thread
    if _started:
        return
    _started = True
    _register()
    _thread = threading.Thread(target=_loop, name="aptitude-registry-heartbeat", daemon=True)
    _thread.start()


def stop() -> None:
    global _started
    if not _started:
        return
    _started = False
    _stop.set()
    try:
        headers = _sign_request("DELETE", "/registry/deregister", b"")
        requests.delete(f"{ORCHESTRATOR_URL}/registry/deregister",
                        params={"agent_name": MANIFEST["agent_name"], "version": MANIFEST["version"]},
                        headers=headers,
                        timeout=REQUEST_TIMEOUT_SECONDS)
    except requests.RequestException:
        pass


atexit.register(stop)
