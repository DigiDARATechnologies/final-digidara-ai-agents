"""Secrets an admin enters on the admin pages, kept encrypted in the database
(AppSecret). The encryption key is derived from JWT_SECRET, so a database dump
alone does not give the secret away; if JWT_SECRET changes, stored secrets can
no longer be read and count as not set until an admin enters them again."""
import base64
import hashlib
import logging

from cryptography.fernet import Fernet, InvalidToken

from app import db
from app.models import AppSecret

logger = logging.getLogger(__name__)


def _fernet() -> Fernet:
    from app.auth.security import JWT_SECRET

    digest = hashlib.sha256(b"skilldara-app-secrets:" + JWT_SECRET.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def hint_for(value: str) -> str:
    """Enough to recognise a key, not enough to use it: 'sk-admin-…abcd'."""
    head = "sk-admin-" if value.startswith("sk-admin-") else value[:3]
    return f"{head}…{value[-4:]}"


def get(name: str) -> str | None:
    session = db.get_session()
    try:
        row = session.get(AppSecret, name)
        if row is None:
            return None
        try:
            return _fernet().decrypt(row.value.encode()).decode()
        except InvalidToken:
            logger.warning("stored secret %s cannot be decrypted (JWT_SECRET changed?)", name)
            return None
    finally:
        session.close()


def info(name: str) -> dict | None:
    session = db.get_session()
    try:
        row = session.get(AppSecret, name)
        if row is None:
            return None
        return {"hint": row.hint, "updated_by": row.updated_by,
                "updated_at": row.updated_at.isoformat() if row.updated_at else None}
    finally:
        session.close()


def put(name: str, value: str, updated_by: str = "") -> None:
    session = db.get_session()
    try:
        token = _fernet().encrypt(value.encode()).decode()
        row = session.get(AppSecret, name)
        if row is None:
            session.add(AppSecret(name=name, value=token, hint=hint_for(value), updated_by=updated_by))
        else:
            row.value, row.hint, row.updated_by = token, hint_for(value), updated_by
        session.commit()
    finally:
        session.close()


def delete(name: str) -> bool:
    session = db.get_session()
    try:
        row = session.get(AppSecret, name)
        if row is None:
            return False
        session.delete(row)
        session.commit()
        return True
    finally:
        session.close()
