"""Strategy F /api/invoke router for certificate_agent."""
from __future__ import annotations

import logging
import json
import uuid
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse, Response, StreamingResponse
from httpx import ASGITransport, AsyncClient

from cert_app.db.database import get_connection
from cert_app.services.auth_service import create_access_token, get_password_hash
from cert_app.services.usage_service import get_usage_summary, record_request

logger = logging.getLogger("certificate.api.invoke")
router = APIRouter()

ACTION_ROUTE_MAP: Dict[str, tuple[str, str]] = {
    "me": ("GET", "/api/auth/me"),
    "start_exam": ("POST", "/api/exam/start"),
    "submit_exam": ("POST", "/api/exam/submit"),
    "get_history": ("GET", "/api/exam/history"),
    "get_leaderboard": ("GET", "/api/exam/leaderboard"),
    "get_exam_detail": ("GET", "/api/exam/{exam_id}"),
    "get_chat_session_questions": ("GET", "/api/exam/chat-session/{session_id}/questions"),
    "get_my_certificates": ("GET", "/api/certificate/my-certificates"),
    "download_certificate": ("GET", "/api/certificate/download/{cert_id}"),
    "interpret_certificate_request": ("POST", "/api/certificate/interpret"),
    "update_certificate_recipient": ("POST", "/api/certificate/{cert_id}/recipient"),
    "request_certificate_email_verification": ("POST", "/api/certificate/{cert_id}/email"),
    "verify_certificate_email": ("POST", "/api/certificate/{cert_id}/email/verify"),
    "start_chat": ("POST", "/api/chat/start"),
    "send_chat_message": ("POST", "/api/chat/message"),
    "get_chat_sessions": ("GET", "/api/chat/sessions"),
    "get_chat_session": ("GET", "/api/chat/session/{session_id}"),
    "recover_chat_certificate": ("POST", "/api/chat/session/{session_id}/certificate"),
}


def _ensure_profile(payload: dict) -> dict:
    """Canonical Strategy F identity bridge for certificate_agent."""
    email = str(payload.get("email") or "").strip().lower()
    name = str(payload.get("name") or "Learner").strip()
    user_id_str = str(payload.get("user_id") or "").strip()

    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="A valid email is required for identity bridge")

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id, name, email, is_active FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        if not user:
            # Create user lazily for dev mode identity bridging
            dummy_pass = uuid.uuid4().hex
            hashed = get_password_hash(dummy_pass)
            cursor.execute(
                "INSERT INTO users (name, email, hashed_password) VALUES (%s, %s, %s)",
                (name or "Learner", email, hashed)
            )
            conn.commit()
            uid = cursor.lastrowid
            cursor.execute("SELECT id, name, email, is_active FROM users WHERE id = %s", (uid,))
            user = cursor.fetchone()
        else:
            if name and user["name"] != name:
                cursor.execute("UPDATE users SET name = %s WHERE id = %s", (name, user["id"]))
                conn.commit()
                user["name"] = name
    finally:
        cursor.close()
        conn.close()

    token = create_access_token({
        "sub": str(user["id"]),
        "name": user["name"],
        "email": user["email"]
    })

    return {
        "status": "ok",
        "access_token": token,
        "sessionToken": token,
        "token": token,
        "user": {
            "id": user["id"],
            "name": user["name"],
            "email": user["email"]
        }
    }


@router.post("/api/invoke")
async def invoke(request: Request) -> Response:
    """
    Common Strategy F dispatcher endpoint. Exempt from CSRF/cookie-based auth.
    Uses in-process test client re-entry to delegate calls to existing FastAPI routes.
    """
    try:
        body = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Request body must be valid JSON") from exc

    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Request body must be a JSON object")

    action = str(body.get("action") or "").strip()
    payload = body.get("payload") or {}
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="payload must be an object")

    if action == "health":
        return JSONResponse({"status": "ok", "agent_name": "certificate_agent", "version": "v1.0.0"})

    if action == "usage_summary":
        return JSONResponse(get_usage_summary())

    if action in ("ensure_profile", "ensure_session"):
        return JSONResponse(_ensure_profile(payload))

    route_info = ACTION_ROUTE_MAP.get(action)
    if not route_info:
        raise HTTPException(status_code=404, detail=f"Unknown action: {action!r}")

    method, path_template = route_info
    clean_payload = payload.copy()

    # Extract auth token from payload if provided
    token = str(clean_payload.pop("sessionToken", "") or clean_payload.pop("token", "") or "").strip()

    # Interpolate path params if any
    try:
        path = path_template.format(**clean_payload)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=f"Missing required path parameter: {exc.args[0]}")

    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    # Re-enter the FastAPI application in-process using ASGITransport
    transport = ASGITransport(app=request.app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        if method == "GET":
            # Pass remaining clean_payload as query parameters for GET requests
            query_params = {k: v for k, v in clean_payload.items() if f"{{{k}}}" not in path_template}
            upstream = await client.get(path, params=query_params, headers=headers)
        elif method == "POST":
            # For POST requests, remove path parameters from payload body
            body_data = {k: v for k, v in clean_payload.items() if f"{{{k}}}" not in path_template}
            upstream = await client.post(path, json=body_data, headers=headers)
        else:
            upstream = await client.request(method, path, json=clean_payload, headers=headers)

    # Special-case binary responses (e.g. download_certificate PDF export) per STRATEGY_F.md
    content_type = upstream.headers.get("content-type", "")
    content_disposition = upstream.headers.get("content-disposition")

    if action == "download_certificate" or "application/pdf" in content_type:
        res_headers = {}
        if content_disposition:
            res_headers["Content-Disposition"] = content_disposition
        return Response(
            content=upstream.content,
            status_code=upstream.status_code,
            media_type="application/pdf",
            headers=res_headers
        )

    # Pass through JSON or SSE streaming / plain response
    response = Response(
        content=upstream.content,
        status_code=upstream.status_code,
        media_type=content_type or "application/json"
    )
    # Count each user-facing certificate-agent action. This deliberately runs
    # after the upstream response so unsuccessful calls are visible too.
    try:
        record_request(action)
    except Exception:
        logger.exception("Could not record certificate usage for action %s", action)
    return response
