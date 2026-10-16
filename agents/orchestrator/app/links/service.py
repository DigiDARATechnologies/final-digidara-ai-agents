"""Links Boss makes on request: a link to one of the learner's chats, and a
short-lived link to download one of their certificates.

A chat link is a random token stored in chat_share_links. "private" opens only
for the account that made it (the viewer must sign in as that account);
"public" opens for any signed-in DigiDARA account. Either way the chat is
shown read-only, as it is when the link is opened.

A certificate link is a signed token (the platform's JWT secret) naming the
owner and the certificate, valid for CERTIFICATE_LINK_SECONDS. Only the owner's
signed-in account can download with it; the PDF is fetched from the
certificate agent through its identity bridge for that same account, and the
agent itself checks the certificate belongs to them.
"""
from __future__ import annotations

import json
import logging
import secrets
import time
from typing import Any
from urllib.parse import urlparse

import httpx
import jwt

from app import config, db
from app.auth.agent_signing import sign_headers
from app.auth.security import JWT_ALGORITHM, JWT_SECRET
from app.models import ChatShareLink, Conversation, ConversationMessage, User
from app.registry import service as registry_service

logger = logging.getLogger("orchestrator.links")

SHARE_MODES = ("private", "public")
CERTIFICATE_LINK_SECONDS = 5 * 60
CERTIFICATE_AGENT = "certificate_agent"
_CERTIFICATE_LINK_TYPE = "certificate_link"


class LinkError(Exception):
    """A link that cannot be used, with the HTTP status and what to tell the viewer."""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def chat_link_path(token: str) -> str:
    return f"/shared/chat/{token}"


def certificate_link_path(token: str) -> str:
    return f"/certificate-link/{token}"


# --- chat links --------------------------------------------------------------

def create_chat_link(user_id: str, chat_id: str, mode: str) -> dict:
    """The link to one of the learner's own chats, for "private" or "public".
    Asking again for the same chat and mode gives the same link."""
    if mode not in SHARE_MODES:
        raise LinkError(422, "A chat link is either private or public.")
    session = db.get_session()
    try:
        chat = (session.query(Conversation)
                .filter_by(id=chat_id, user_id=user_id, deleted_at=None).one_or_none())
        if chat is None:
            raise LinkError(404, "That chat was not found in your account.")
        link = (session.query(ChatShareLink)
                .filter_by(user_id=user_id, conversation_id=chat_id, mode=mode).first())
        if link is None:
            link = ChatShareLink(token=secrets.token_urlsafe(24), user_id=user_id, conversation_id=chat_id, mode=mode)
            session.add(link)
            session.commit()
        return {"kind": "chat", "mode": mode, "title": chat.title, "path": chat_link_path(link.token)}
    finally:
        session.close()


def read_shared_chat(token: str, viewer_id: str) -> dict:
    """The chat behind a link, read-only, if this viewer may open it."""
    session = db.get_session()
    try:
        link = session.get(ChatShareLink, token)
        if link is None:
            raise LinkError(404, "This chat link does not exist or was removed.")
        is_owner = link.user_id == viewer_id
        if link.mode == "private" and not is_owner:
            raise LinkError(403, "This chat link is private. Only the account that made it can open it: "
                                 "sign in with that account.")
        chat = (session.query(Conversation)
                .filter_by(id=link.conversation_id, user_id=link.user_id, deleted_at=None).one_or_none())
        if chat is None:
            raise LinkError(404, "The chat behind this link was deleted.")
        rows = (session.query(ConversationMessage)
                .filter_by(conversation_id=chat.id, user_id=link.user_id)
                .order_by(ConversationMessage.position).all())
        owner = session.get(User, link.user_id)
        first_name = ((owner.name or "").split() or [""])[0] if owner else ""
        return {
            "title": chat.title,
            "agent_id": chat.agent_id,
            "mode": link.mode,
            "is_owner": is_owner,
            "owner_name": first_name,
            "chat_id": chat.id if is_owner else None,
            "messages": [{"role": row.role, "text": row.content, "time": row.display_time} for row in rows],
        }
    finally:
        session.close()


def purge(user_id: str) -> None:
    session = db.get_session()
    try:
        session.query(ChatShareLink).filter_by(user_id=user_id).delete()
        session.commit()
    finally:
        session.close()


# --- certificate links -------------------------------------------------------

def create_certificate_link(user_id: str, cert_id: str, title: str = "") -> dict:
    now = int(time.time())
    token = jwt.encode(
        {"typ": _CERTIFICATE_LINK_TYPE, "sub": user_id, "cert": str(cert_id), "iat": now,
         "exp": now + CERTIFICATE_LINK_SECONDS},
        JWT_SECRET, algorithm=JWT_ALGORITHM,
    )
    return {"kind": "certificate", "title": title, "path": certificate_link_path(token),
            "expires_at": (now + CERTIFICATE_LINK_SECONDS) * 1000, "expires_in": CERTIFICATE_LINK_SECONDS}


def certificate_link_owner(token: str, viewer_id: str) -> str:
    """The certificate id a link is for, once it is checked to be unexpired
    and opened by the account it was made for."""
    try:
        claims = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise LinkError(410, "This certificate link has expired (links last 5 minutes). Ask Boss for a new one.") from exc
    except jwt.PyJWTError as exc:
        raise LinkError(404, "This certificate link is not valid.") from exc
    if claims.get("typ") != _CERTIFICATE_LINK_TYPE or not claims.get("cert"):
        raise LinkError(404, "This certificate link is not valid.")
    if claims.get("sub") != viewer_id:
        raise LinkError(403, "Only the certificate's owner can download it with this link. "
                             "Sign in with the account that earned the certificate.")
    return str(claims["cert"])


def _certificate_endpoint() -> str:
    from app.gateway.routes import ALLOWED_AGENT_HOSTS

    agent = registry_service.resolve_healthy(CERTIFICATE_AGENT)
    if agent is None or urlparse(agent.endpoint).hostname not in ALLOWED_AGENT_HOSTS:
        raise LinkError(503, "AI Certification is not reachable right now. Please try again in a minute.")
    return agent.endpoint


def _invoke_certificate_agent(user: User, action: str, payload: dict) -> httpx.Response:
    endpoint = _certificate_endpoint()
    body = json.dumps({"action": action, "payload": payload}).encode()
    try:
        return httpx.post(endpoint, content=body, timeout=config.AGENT_CALL_TIMEOUT_SECONDS, headers={
            "Content-Type": "application/json",
            "X-Digidara-User-Id": user.id,
            "X-Digidara-Is-Admin": "false",
            **sign_headers(CERTIFICATE_AGENT, "POST", endpoint, body, user.id, "false"),
        })
    except httpx.HTTPError as exc:
        raise LinkError(503, "AI Certification is not reachable right now. Please try again in a minute.") from exc


def _certificate_session(user: User) -> str:
    """The certificate agent's own session for this verified account."""
    response = _invoke_certificate_agent(
        user, "ensure_session", {"user_id": user.id, "name": user.name, "email": user.email, "mobile": user.mobile or ""})
    try:
        token = response.json().get("sessionToken") if response.is_success else None
    except ValueError:
        token = None
    if not token:
        raise LinkError(503, "AI Certification could not open your account just now. Please try again.")
    return token


def own_certificates(user: User) -> list[dict[str, Any]]:
    """The learner's own certificates, newest first (id, topic, number, score, issued)."""
    response = _invoke_certificate_agent(user, "get_my_certificates", {"sessionToken": _certificate_session(user)})
    try:
        rows = response.json() if response.is_success else []
    except ValueError:
        rows = []
    return [
        {"id": str(row.get("id")), "topic": row.get("topic"), "certificate_number": row.get("certificate_number"),
         "score_percentage": row.get("score_percentage"), "issued_at": row.get("issued_at")}
        for row in rows if isinstance(row, dict) and row.get("id") is not None
    ]


def download_certificate(user: User, cert_id: str) -> tuple[bytes, str]:
    """The certificate PDF and its file name. The agent only returns a
    certificate that belongs to this account."""
    try:
        number = int(cert_id)
    except ValueError as exc:
        raise LinkError(404, "This certificate link is not valid.") from exc
    response = _invoke_certificate_agent(
        user, "download_certificate", {"sessionToken": _certificate_session(user), "cert_id": number})
    if response.status_code == 404:
        raise LinkError(404, "That certificate was not found in your account.")
    if not response.is_success or "application/pdf" not in response.headers.get("content-type", ""):
        raise LinkError(502, "The certificate could not be downloaded just now. Please try again.")
    disposition = response.headers.get("content-disposition", "")
    name = disposition.split("filename=")[-1].strip('"; ') if "filename=" in disposition else f"certificate_{number}.pdf"
    return response.content, name
