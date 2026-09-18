"""Flask-friendly Strategy F registration and heartbeat client."""
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

logger = logging.getLogger("resume_builder.integration.registry")
AGENT_ROOT = Path(__file__).resolve().parents[1]
MANIFEST = json.loads((AGENT_ROOT / "manifest.json").read_text(encoding="utf-8"))
_stop = threading.Event()
_lock = threading.Lock()
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


def _setting(name: str, default: str) -> str:
    return os.getenv(name, default).strip()


def _endpoint() -> str:
    configured = _setting("AGENT_PUBLIC_URL", "")
    if configured:
        return configured.rstrip("/")
    return f"http://{MANIFEST['host']}:{MANIFEST['port']}{MANIFEST['path']}"


def registration_payload() -> dict:
    return {
        "agent_name": _setting("AGENT_NAME", MANIFEST["agent_name"]),
        "version": _setting("AGENT_VERSION", MANIFEST["version"]),
        "endpoint": _endpoint(),
        "description": MANIFEST["description"],
        "input_schema": MANIFEST["input_schema"],
        "output_schema": MANIFEST.get("output_schema", {}),
        "owner": MANIFEST.get("owner"),
        "plan_tier": MANIFEST.get("plan_tier", "free"),
    }


def _url(path: str) -> str:
    return _setting("ORCHESTRATOR_URL", "http://127.0.0.1:8100").rstrip("/") + path


def _post_register() -> bool:
    body = json.dumps(registration_payload()).encode("utf-8")
    headers = {"Content-Type": "application/json", **_sign_request("POST", "/registry/register", body)}
    try:
        response = requests.post(_url("/registry/register"), data=body, headers=headers, timeout=10)
        response.raise_for_status()
        logger.info("registered Resume Builder with the orchestrator")
        return True
    except requests.RequestException as exc:
        logger.warning("Resume Builder registration failed; retrying in the heartbeat loop: %s", exc)
        return False


def _heartbeat() -> None:
    payload = registration_payload()
    # Includes `endpoint` (not just agent_name/version) so a long-lived
    # process whose AGENT_PUBLIC_URL was corrected after it last started
    # self-heals on the next heartbeat instead of staying registered under a
    # stale endpoint indefinitely -- _post_register() only runs once at boot.
    body = json.dumps({"agent_name": payload["agent_name"], "version": payload["version"], "endpoint": payload["endpoint"]}).encode("utf-8")
    headers = {"Content-Type": "application/json", **_sign_request("POST", "/registry/heartbeat", body)}
    try:
        response = requests.post(_url("/registry/heartbeat"), data=body, headers=headers, timeout=10)
        if response.status_code == 404:
            _post_register()
        else:
            response.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("Resume Builder heartbeat failed: %s", exc)


def _loop() -> None:
    normal_delay = max(1, int(_setting("HEARTBEAT_INTERVAL_SECONDS", "30")))
    delay = normal_delay
    while not _stop.wait(delay):
        # Registration failures are retried with a bounded backoff while a
        # healthy connection returns to the configured heartbeat interval.
        try:
            payload = registration_payload()
            # Includes `endpoint` so a long-lived process whose
            # AGENT_PUBLIC_URL was corrected after it last started self-heals
            # on the next heartbeat instead of staying registered under a
            # stale endpoint indefinitely -- _post_register() only runs once
            # at boot (or on a 404 here).
            body = json.dumps({"agent_name": payload["agent_name"], "version": payload["version"], "endpoint": payload["endpoint"]}).encode("utf-8")
            headers = {"Content-Type": "application/json", **_sign_request("POST", "/registry/heartbeat", body)}
            response = requests.post(_url("/registry/heartbeat"), data=body, headers=headers, timeout=10)
            if response.status_code == 404:
                success = _post_register()
            else:
                response.raise_for_status()
                success = True
        except requests.RequestException as exc:
            logger.warning("Resume Builder heartbeat failed: %s", exc)
            success = False
        delay = normal_delay if success else min(max(normal_delay, delay * 2), 300)


def start() -> None:
    """Register and start exactly one daemon heartbeat thread."""
    global _started, _thread
    with _lock:
        if _started:
            return
        _started = True
        _stop.clear()
        _post_register()
        _thread = threading.Thread(target=_loop, name="resume-builder-heartbeat", daemon=True)
        _thread.start()


def stop() -> None:
    global _started
    with _lock:
        if not _started:
            return
        _started = False
        _stop.set()
    payload = registration_payload()
    try:
        headers = _sign_request("DELETE", "/registry/deregister", b"")
        requests.delete(_url("/registry/deregister"), params={"agent_name": payload["agent_name"], "version": payload["version"]}, headers=headers, timeout=10)
    except requests.RequestException:
        logger.debug("Resume Builder deregistration could not be sent", exc_info=True)


atexit.register(stop)
