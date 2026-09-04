from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import os
import time
import uuid
from contextlib import suppress
from pathlib import Path

import httpx

logger = logging.getLogger("capstone.registry")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MANIFEST = json.loads((PROJECT_ROOT / "manifest.json").read_text(encoding="utf-8"))
ORCHESTRATOR_URL = os.environ.get("ORCHESTRATOR_URL", "http://127.0.0.1:8100").rstrip("/")
HEARTBEAT_INTERVAL_SECONDS = int(os.environ.get("HEARTBEAT_INTERVAL_SECONDS", "30"))

# Must match the orchestrator's own AGENT_SHARED_SECRET (app/auth/service_auth.py)
# and its dev-mode default — every agent's registry_client.py shares this same
# fallback so local dev works with no .env changes.
AGENT_SHARED_SECRET = os.environ.get("AGENT_SHARED_SECRET", "dev-only-agent-shared-secret")


def _sign_request(method: str, path: str, body: bytes) -> dict[str, str]:
    timestamp = str(int(time.time()))
    request_id = uuid.uuid4().hex
    body_hash = hashlib.sha256(body).hexdigest()
    canonical = "\n".join((timestamp, request_id, method.upper(), path, body_hash))
    signature = hmac.new(AGENT_SHARED_SECRET.encode(), canonical.encode(), hashlib.sha256).hexdigest()
    return {"X-Agent-Timestamp": timestamp, "X-Agent-Request-Id": request_id, "X-Agent-Signature": signature}


def _registration_payload() -> dict:
    endpoint = os.environ.get("AGENT_PUBLIC_URL")
    if not endpoint:
        endpoint = f"http://{MANIFEST['host']}:{MANIFEST['port']}{MANIFEST.get('path', '/invoke')}"
    return {
        "agent_name": MANIFEST["agent_name"],
        "version": MANIFEST["version"],
        "endpoint": endpoint,
        "description": MANIFEST["description"],
        "input_schema": MANIFEST["input_schema"],
        "output_schema": MANIFEST.get("output_schema", {}),
        "owner": MANIFEST.get("owner"),
        "plan_tier": MANIFEST.get("plan_tier", "free"),
    }


class RegistryClient:
    def __init__(self) -> None:
        self._heartbeat_task: asyncio.Task | None = None

    async def _register(self) -> bool:
        try:
            body = json.dumps(_registration_payload()).encode("utf-8")
            headers = {"content-type": "application/json", **_sign_request("POST", "/registry/register", body)}
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(f"{ORCHESTRATOR_URL}/registry/register", content=body, headers=headers)
                response.raise_for_status()
            logger.info("registered %s with %s", MANIFEST["agent_name"], ORCHESTRATOR_URL)
            return True
        except Exception:
            logger.warning("registry unavailable at %s; registration will retry", ORCHESTRATOR_URL)
            return False

    async def _heartbeat_loop(self) -> None:
        while True:
            await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)
            try:
                body = json.dumps({"agent_name": MANIFEST["agent_name"], "version": MANIFEST["version"]}).encode("utf-8")
                headers = {"content-type": "application/json", **_sign_request("POST", "/registry/heartbeat", body)}
                async with httpx.AsyncClient(timeout=10) as client:
                    response = await client.post(
                        f"{ORCHESTRATOR_URL}/registry/heartbeat",
                        content=body,
                        headers=headers,
                    )
                if response.status_code == 404:
                    await self._register()
                else:
                    response.raise_for_status()
            except Exception:
                logger.warning("registry heartbeat failed; retrying in %ss", HEARTBEAT_INTERVAL_SECONDS)

    async def start(self) -> None:
        await self._register()
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def stop(self) -> None:
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._heartbeat_task
        try:
            headers = _sign_request("DELETE", "/registry/deregister", b"")
            async with httpx.AsyncClient(timeout=5) as client:
                await client.request(
                    "DELETE",
                    f"{ORCHESTRATOR_URL}/registry/deregister",
                    params={"agent_name": MANIFEST["agent_name"], "version": MANIFEST["version"]},
                    headers=headers,
                )
        except Exception:
            pass


registry_client = RegistryClient()
