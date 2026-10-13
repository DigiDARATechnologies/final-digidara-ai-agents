"""A2A client for the orchestrator's own services (the readiness service).

Builds real A2A `message/send` requests and reads the returned Task, going
through the hub in-process -- the same JSON-RPC handling an outside client
gets over HTTP, without a network hop back into this process.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.a2a import hub
from app.a2a import protocol as p


@dataclass
class A2AResult:
    state: str
    data: Any
    error: str | None
    task: dict | None


def _first_data(task: dict) -> Any:
    for artifact in task.get("artifacts") or []:
        for part in artifact.get("parts") or []:
            if part.get("kind") == "data":
                return part.get("data")
            if part.get("kind") == "text":
                return part.get("text")
    return None


async def send(agent_name: str, action: str, payload: dict, user, caller: str) -> A2AResult:
    request = {
        "jsonrpc": p.JSONRPC,
        "id": p.new_id(),
        "method": "message/send",
        "params": {
            "message": {
                "kind": "message", "role": "user", "messageId": p.new_id(),
                "parts": [p.data_part({"action": action, "payload": payload})],
            },
        },
    }
    response = await hub.handle(agent_name, request, user, caller)
    if "error" in response:
        return A2AResult("error", None, response["error"].get("message"), None)
    task = response["result"]
    state = task["status"]["state"]
    error = None
    if state != "completed":
        message = task["status"].get("message") or {}
        error = next((part.get("text") for part in message.get("parts", []) if part.get("kind") == "text"), None)
    return A2AResult(state, _first_data(task), error, task)
