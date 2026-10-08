"""The A2A hub: JSON-RPC methods for every registered agent.

`message/send` to /a2a/<agent> runs that agent's action through the same
gateway path the browser uses (gateway.invoke_json): live-registry routing,
host allow-list, billing, signed identity headers and the learner context.
Agents answer synchronously, so the returned Task is already terminal; it is
stored so `tasks/get` can return it later.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any

from fastapi import HTTPException

from app import db
from app.a2a import protocol as p
from app.a2a.cards import READINESS_AGENT
from app.gateway import routes as gateway
from app.models import A2ATask

logger = logging.getLogger("orchestrator.a2a")

TASK_RETENTION = timedelta(days=7)
SUPPORTED_METHODS = ("message/send", "tasks/get", "tasks/cancel")


def _save(task: dict, user_id: str, agent_name: str, caller: str) -> None:
    session = db.get_session()
    try:
        row = session.get(A2ATask, task["id"])
        if row is None:
            row = A2ATask(id=task["id"], context_id=task["contextId"], user_id=user_id, agent_name=agent_name, caller=caller)
            session.add(row)
        row.state = task["status"]["state"]
        row.task = task
        row.updated_at = datetime.utcnow()
        session.query(A2ATask).filter(A2ATask.created_at < datetime.utcnow() - TASK_RETENTION).delete()
        session.commit()
    finally:
        session.close()


def _load(task_id: str, user_id: str) -> dict | None:
    session = db.get_session()
    try:
        row = session.get(A2ATask, task_id)
        # Another learner's task id reads as "not found", never as forbidden.
        return dict(row.task) if row is not None and row.user_id == user_id else None
    finally:
        session.close()


def _artifacts_from_response(response) -> tuple[list[dict], Any]:
    content_type = (response.headers.get("content-type") or "").split(";")[0].strip()
    if content_type == "application/json":
        try:
            data = json.loads(response.body)
        except ValueError:
            data = None
        if data is not None:
            return [p.artifact([p.data_part(data)])], data
    if content_type.startswith("text/"):
        text = response.body.decode("utf-8", "replace")
        return [p.artifact([p.text_part(text)])], text
    name = None
    disposition = response.headers.get("content-disposition") or ""
    if "filename=" in disposition:
        name = disposition.split("filename=", 1)[1].strip('"; ')
    return [p.artifact([p.file_part(response.body, content_type or "application/octet-stream", name)])], None


def _error_text(data: Any, status_code: int) -> str:
    if isinstance(data, dict):
        for key in ("detail", "error", "message"):
            if isinstance(data.get(key), str):
                return data[key]
    return f"The agent answered with status {status_code}."


async def _run_agent(agent_name: str, action: str, payload: dict, user, caller: str, task_id: str, context_id: str) -> dict:
    if agent_name == READINESS_AGENT:
        from app.readiness import service as readiness_service  # local import: readiness uses this hub

        data = await readiness_service.skill(action, user)
        return p.task(task_id, context_id, "completed", artifacts=[p.artifact([p.data_part(data)])])
    try:
        response = await gateway.invoke_json(agent_name, action, payload, user, caller=None if caller == "user" else caller)
    except HTTPException as exc:
        # 402 (no points), 503 (agent down), 504 (timeout): the call was
        # accepted but could not run -- a failed task, not a protocol error.
        return p.task(task_id, context_id, "failed", status_text=str(exc.detail), metadata={"http_status": exc.status_code})
    artifacts, data = _artifacts_from_response(response)
    if response.status_code >= 400:
        return p.task(
            task_id, context_id, "failed", artifacts=artifacts,
            status_text=_error_text(data, response.status_code), metadata={"http_status": response.status_code},
        )
    return p.task(task_id, context_id, "completed", artifacts=artifacts, metadata={"http_status": response.status_code})


async def handle(agent_name: str, rpc: Any, user, caller: str = "user") -> dict:
    """One JSON-RPC request in, one JSON-RPC response out. Never raises."""
    request_id = rpc.get("id") if isinstance(rpc, dict) else None
    try:
        if not isinstance(rpc, dict) or rpc.get("jsonrpc") != p.JSONRPC or not isinstance(rpc.get("method"), str):
            raise p.RpcError(p.INVALID_REQUEST, "Expected a JSON-RPC 2.0 request object.")
        method = rpc["method"]
        params = rpc.get("params")

        if method == "message/send":
            action, payload, message = p.parse_invocation(params)
            task_id = message.get("taskId") if isinstance(message.get("taskId"), str) else p.new_id()
            context_id = message.get("contextId") if isinstance(message.get("contextId"), str) else p.new_id()
            if _load(task_id, user.id) is not None:
                raise p.RpcError(p.UNSUPPORTED_OPERATION, "Tasks here complete in one call; start a new task instead.")
            result = await _run_agent(agent_name, action, payload, user, caller, task_id, context_id)
            result["history"] = [{**message, "taskId": task_id, "contextId": context_id}]
            _save(result, user.id, agent_name, caller)
            logger.info("a2a message/send agent=%s action=%s caller=%s state=%s", agent_name, action, caller, result["status"]["state"])
            return p.rpc_result(request_id, result)

        if method == "tasks/get":
            task_id = params.get("id") if isinstance(params, dict) else None
            if not isinstance(task_id, str):
                raise p.RpcError(p.INVALID_PARAMS, "params.id is required.")
            found = _load(task_id, user.id)
            if found is None:
                raise p.RpcError(p.TASK_NOT_FOUND, "Task not found.")
            history_length = params.get("historyLength")
            if isinstance(history_length, int) and history_length >= 0:
                found["history"] = found.get("history", [])[-history_length:] if history_length else []
            return p.rpc_result(request_id, found)

        if method == "tasks/cancel":
            task_id = params.get("id") if isinstance(params, dict) else None
            found = _load(task_id, user.id) if isinstance(task_id, str) else None
            if found is None:
                raise p.RpcError(p.TASK_NOT_FOUND, "Task not found.")
            raise p.RpcError(p.TASK_NOT_CANCELABLE, "This task has already finished.")

        if method in ("message/stream", "tasks/resubscribe") or method.startswith("tasks/pushNotificationConfig/"):
            raise p.RpcError(p.UNSUPPORTED_OPERATION, f"{method} is not supported; see capabilities in the agent card.")
        raise p.RpcError(p.METHOD_NOT_FOUND, f"Unknown method {method!r}. Supported: {', '.join(SUPPORTED_METHODS)}.")
    except p.RpcError as error:
        return p.rpc_error(request_id, error)
    except Exception:
        logger.exception("a2a request failed agent=%s", agent_name)
        return p.rpc_error(request_id, p.RpcError(p.INTERNAL_ERROR, "The hub could not complete this request."))
