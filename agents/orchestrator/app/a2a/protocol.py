"""A2A (Agent2Agent) protocol objects, JSON-RPC 2.0 binding.

Follows the A2A specification (https://a2a-protocol.org, protocol 0.3): an
Agent Card describes an agent; `message/send` carries a Message made of Parts
and returns a Task whose Artifacts hold the result; `tasks/get` reads a Task
back. Only the shapes this hub produces and accepts are modelled here.
"""
from __future__ import annotations

import base64
import uuid
from datetime import datetime, timezone
from typing import Any

PROTOCOL_VERSION = "0.3.0"
JSONRPC = "2.0"

# JSON-RPC 2.0 and A2A error codes.
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603
TASK_NOT_FOUND = -32001
TASK_NOT_CANCELABLE = -32002
UNSUPPORTED_OPERATION = -32004

TERMINAL_STATES = frozenset({"completed", "failed", "canceled", "rejected"})


class RpcError(Exception):
    def __init__(self, code: int, message: str, data: Any = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data


def new_id() -> str:
    return uuid.uuid4().hex


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def rpc_result(request_id: Any, result: dict) -> dict:
    return {"jsonrpc": JSONRPC, "id": request_id, "result": result}


def rpc_error(request_id: Any, error: RpcError) -> dict:
    body: dict[str, Any] = {"code": error.code, "message": error.message}
    if error.data is not None:
        body["data"] = error.data
    return {"jsonrpc": JSONRPC, "id": request_id, "error": body}


def text_part(text: str) -> dict:
    return {"kind": "text", "text": text}


def data_part(data: Any) -> dict:
    return {"kind": "data", "data": data}


def file_part(content: bytes, mime_type: str, name: str | None = None) -> dict:
    file: dict[str, Any] = {"bytes": base64.b64encode(content).decode("ascii"), "mimeType": mime_type}
    if name:
        file["name"] = name
    return {"kind": "file", "file": file}


def agent_message(parts: list[dict], context_id: str, task_id: str) -> dict:
    return {
        "kind": "message", "role": "agent", "messageId": new_id(),
        "parts": parts, "contextId": context_id, "taskId": task_id,
    }


def task(task_id: str, context_id: str, state: str, *, artifacts: list[dict] | None = None,
         status_text: str | None = None, history: list[dict] | None = None, metadata: dict | None = None) -> dict:
    status: dict[str, Any] = {"state": state, "timestamp": now_iso()}
    if status_text:
        status["message"] = agent_message([text_part(status_text)], context_id, task_id)
    result: dict[str, Any] = {"kind": "task", "id": task_id, "contextId": context_id, "status": status}
    if artifacts:
        result["artifacts"] = artifacts
    if history:
        result["history"] = history
    if metadata:
        result["metadata"] = metadata
    return result


def artifact(parts: list[dict], name: str = "result") -> dict:
    return {"artifactId": new_id(), "name": name, "parts": parts}


def parse_invocation(params: Any) -> tuple[str, dict, dict]:
    """(action, payload, message) from `message/send` params.

    The agent action travels as a data part `{"action": ..., "payload": {...}}`
    -- the same {action, payload} contract every DigiDARA agent already
    serves. A text-only message may name the action in `metadata.action`;
    its text then becomes `payload.message`.
    """
    if not isinstance(params, dict) or not isinstance(params.get("message"), dict):
        raise RpcError(INVALID_PARAMS, "params.message is required.")
    message = params["message"]
    parts = message.get("parts")
    if not isinstance(parts, list) or not parts:
        raise RpcError(INVALID_PARAMS, "message.parts must be a non-empty list.")
    for part in parts:
        if isinstance(part, dict) and part.get("kind") == "data" and isinstance(part.get("data"), dict):
            data = part["data"]
            action = data.get("action")
            if isinstance(action, str) and action.strip():
                payload = data.get("payload") if isinstance(data.get("payload"), dict) else {}
                return action.strip(), payload, message
    metadata = params.get("metadata") if isinstance(params.get("metadata"), dict) else {}
    action = metadata.get("action") or (message.get("metadata") or {}).get("action")
    texts = [p.get("text", "") for p in parts if isinstance(p, dict) and p.get("kind") == "text"]
    if isinstance(action, str) and action.strip() and texts:
        return action.strip(), {"message": "\n".join(texts)}, message
    raise RpcError(
        INVALID_PARAMS,
        'Send a data part {"action": "<skill id>", "payload": {...}}, or a text part with metadata.action.',
    )
