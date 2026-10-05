"""The "email verified" gate for everything that uses the agents.

The frontend shows a verify screen, but the server is what enforces it: an
account that must verify (auth/email_verification.py) gets 403 from the
agent gateway, the general chat and voice until it does.
"""
from fastapi import Depends, HTTPException, status

from app.auth import email_verification
from app.auth import service as auth_service
from app.auth.security import get_current_user_id

NOT_VERIFIED_DETAIL = "Please verify your email to use DigiDARA's agents."


def ensure_verified(user) -> None:
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "This account no longer exists.")
    if not email_verification.is_verified(user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, NOT_VERIFIED_DETAIL)


def get_verified_user_id(user_id: str = Depends(get_current_user_id)) -> str:
    ensure_verified(auth_service.get_by_id(user_id))
    return user_id
