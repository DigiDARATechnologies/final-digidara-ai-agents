"""Sign-ins: each one gets a row and its id goes into the session token
("sid"), so Settings > Security can list the devices signed in, sign one out,
or sign out everywhere else. The rows double as the login history and are
never deleted while the account exists."""
from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import Request

from app import db
from app.auth.security import JWT_EXPIRES_MINUTES, create_access_token
from app.models import User, UserSignIn


def _client(request: Request | None) -> tuple[str | None, str | None]:
    if request is None:
        return None, None
    ip = request.client.host if request.client else None
    agent = (request.headers.get("user-agent") or "")[:400] or None
    return ip, agent


def issue_token(user: User, request: Request | None, method: str) -> str:
    """Record a sign-in and return its session token."""
    ip, agent = _client(request)
    version = int(user.session_version or 0)
    session = db.get_session()
    try:
        row = UserSignIn(user_id=user.id, method=method, ip=ip, user_agent=agent, session_version=version)
        session.add(row)
        session.commit()
        sign_in_id = row.id
    finally:
        session.close()
    return create_access_token(user.id, version, sign_in_id)


def token_for_session(user_id: str, session_id: str | None) -> str:
    """A fresh token for this same device, after the account's session version
    changed (password change, sign out everywhere else)."""
    session = db.get_session()
    try:
        user = session.get(User, user_id)
        version = int(user.session_version or 0) if user else 0
        row = session.get(UserSignIn, session_id) if session_id else None
        if row is not None and row.user_id == user_id:
            row.session_version = version
            session.commit()
    finally:
        session.close()
    return create_access_token(user_id, version, session_id)


def _device(agent: str | None) -> str:
    """'Chrome on Windows' from a user-agent string; good enough to recognise a device."""
    text = agent or ""
    browser = ("Edge" if "Edg/" in text else "Opera" if "OPR/" in text else "Samsung Internet" if "SamsungBrowser" in text
               else "Chrome" if "Chrome/" in text else "Firefox" if "Firefox/" in text
               else "Safari" if "Safari/" in text else "")
    system = ("Android" if "Android" in text else "iPhone" if "iPhone" in text else "iPad" if "iPad" in text
              else "Windows" if "Windows" in text else "Mac" if "Mac OS" in text else "Linux" if "Linux" in text else "")
    if browser and system:
        return f"{browser} on {system}"
    return browser or system or "Unknown device"


def list_for(user_id: str, current_id: str | None, now: datetime | None = None) -> list[dict]:
    """Every sign-in, newest first. `active` is whether its token still works:
    not signed out, not expired, and issued at the account's current session
    version."""
    now = now or datetime.utcnow()
    session = db.get_session()
    try:
        user = session.get(User, user_id)
        version = int(user.session_version or 0) if user else -1
        rows = session.query(UserSignIn).filter_by(user_id=user_id).order_by(UserSignIn.created_at.desc()).all()
        expiry = timedelta(minutes=JWT_EXPIRES_MINUTES)
        return [{
            "id": row.id,
            "method": row.method,
            "device": _device(row.user_agent),
            "ip": row.ip,
            "created_at": row.created_at.isoformat() + "Z",
            "revoked_at": row.revoked_at.isoformat() + "Z" if row.revoked_at else None,
            "active": row.revoked_at is None and row.created_at + expiry > now and int(row.session_version or 0) == version,
            "current": row.id == current_id,
        } for row in rows]
    finally:
        session.close()


def revoke(user_id: str, sign_in_id: str) -> bool:
    session = db.get_session()
    try:
        row = session.get(UserSignIn, sign_in_id)
        if row is None or row.user_id != user_id:
            return False
        if row.revoked_at is None:
            row.revoked_at = datetime.utcnow()
            session.commit()
        return True
    finally:
        session.close()


def sign_out_others(user_id: str, current_id: str | None) -> str:
    """Bump the session version, so every token stops working, and return a
    new token for this device."""
    session = db.get_session()
    try:
        user = session.get(User, user_id, with_for_update=True)
        if user is None:
            raise LookupError(user_id)
        user.session_version = (user.session_version or 0) + 1
        session.commit()
    finally:
        session.close()
    return token_for_session(user_id, current_id)


def purge(user_id: str) -> None:
    session = db.get_session()
    try:
        session.query(UserSignIn).filter_by(user_id=user_id).delete()
        session.commit()
    finally:
        session.close()


def export(user_id: str) -> list[dict]:
    return [{k: v for k, v in row.items() if k != "current"} for row in list_for(user_id, None)]
