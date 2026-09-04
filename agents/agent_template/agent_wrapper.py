"""Shared agent-service wrapper — self-registers with the DigiDARA
orchestrator on boot, heartbeats on an interval, deregisters on shutdown, and
exposes the two routes every agent needs: GET /health and POST /invoke.

Copy this file as-is into your own agent's project. You should not need to
edit it — configure via manifest.json and .env instead.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Awaitable, Callable

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException

load_dotenv()

logger = logging.getLogger("agent_wrapper")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s: %(message)s", datefmt="%H:%M:%S")

ORCHESTRATOR_URL = os.environ.get("ORCHESTRATOR_URL", "http://127.0.0.1:8100")
HEARTBEAT_INTERVAL_SECONDS = int(os.environ.get("HEARTBEAT_INTERVAL_SECONDS", 30))

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

InvokeFn = Callable[[dict], "dict | Awaitable[dict]"]

_REQUIRED_MANIFEST_KEYS = {"agent_name", "version", "description", "input_schema", "host", "port"}


def _load_manifest(manifest_path: Path) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    missing = _REQUIRED_MANIFEST_KEYS - manifest.keys()
    if missing:
        raise ValueError(f"manifest.json is missing required keys: {sorted(missing)}")
    return manifest


def _registration_payload(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "agent_name": manifest["agent_name"],
        "version": manifest["version"],
        "endpoint": f"http://{manifest['host']}:{manifest['port']}/invoke",
        "description": manifest["description"],
        "input_schema": manifest["input_schema"],
        "output_schema": manifest.get("output_schema", {}),
        "owner": manifest.get("owner"),
        "plan_tier": manifest.get("plan_tier", "free"),
    }


async def _register(manifest: dict[str, Any]) -> None:
    body = json.dumps(_registration_payload(manifest)).encode("utf-8")
    headers = {"content-type": "application/json", **_sign_request("POST", "/registry/register", body)}
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.post(f"{ORCHESTRATOR_URL}/registry/register", content=body, headers=headers)
            resp.raise_for_status()
            logger.info(
                "registered with orchestrator: %s@%s -> %s",
                manifest["agent_name"], manifest["version"], _registration_payload(manifest)["endpoint"],
            )
        except Exception:
            # The agent still runs and answers /invoke directly either way —
            # it's just unreachable via the orchestrator's /chat until this
            # succeeds (retried automatically on the next heartbeat tick).
            logger.exception("could not reach orchestrator at %s to register", ORCHESTRATOR_URL)


async def _heartbeat_loop(manifest: dict[str, Any]) -> None:
    async with httpx.AsyncClient(timeout=10) as client:
        while True:
            await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)
            body = json.dumps({"agent_name": manifest["agent_name"], "version": manifest["version"]}).encode("utf-8")
            headers = {"content-type": "application/json", **_sign_request("POST", "/registry/heartbeat", body)}
            try:
                resp = await client.post(f"{ORCHESTRATOR_URL}/registry/heartbeat", content=body, headers=headers)
                if resp.status_code == 404:
                    # Orchestrator restarted / lost this row — re-register instead of looping 404s forever.
                    await _register(manifest)
                else:
                    resp.raise_for_status()
            except Exception:
                logger.warning("heartbeat to orchestrator failed (will retry in %ds)", HEARTBEAT_INTERVAL_SECONDS)


async def _deregister(manifest: dict[str, Any]) -> None:
    headers = _sign_request("DELETE", "/registry/deregister", b"")
    async with httpx.AsyncClient(timeout=5) as client:
        try:
            await client.request(
                "DELETE",
                f"{ORCHESTRATOR_URL}/registry/deregister",
                params={"agent_name": manifest["agent_name"], "version": manifest["version"]},
                headers=headers,
            )
        except Exception:
            pass  # best-effort — the heartbeat TTL cleans this up on its own otherwise


def create_agent_app(manifest_path: str | Path, invoke_fn: InvokeFn) -> FastAPI:
    """Build a ready-to-run FastAPI app for one agent.

    `invoke_fn` receives the JSON body of a POST /invoke call and returns a
    JSON-serializable dict (sync or async — both are fine). It is your
    agent's actual logic: wrap a LangGraph `.invoke()`, an LLM call,
    anything. The wrapper does not validate the body against input_schema
    itself — that schema is advisory metadata the orchestrator's LLM router
    reads to decide *whether* to call you; your own `invoke_fn` is still
    responsible for validating what it receives.
    """
    manifest = _load_manifest(Path(manifest_path))
    heartbeat_task: asyncio.Task | None = None

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        nonlocal heartbeat_task
        await _register(manifest)
        heartbeat_task = asyncio.create_task(_heartbeat_loop(manifest))
        yield
        if heartbeat_task:
            heartbeat_task.cancel()
        await _deregister(manifest)

    app = FastAPI(title=manifest["agent_name"], version=manifest["version"], lifespan=lifespan)

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "agent_name": manifest["agent_name"], "version": manifest["version"]}

    @app.post("/invoke")
    async def invoke(payload: dict) -> dict:
        try:
            result = invoke_fn(payload)
            if asyncio.iscoroutine(result):
                result = await result
            return result
        except Exception as exc:
            logger.exception("invoke failed for agent_name=%s", manifest["agent_name"])
            raise HTTPException(500, f"{manifest['agent_name']} failed: {exc}")

    return app
