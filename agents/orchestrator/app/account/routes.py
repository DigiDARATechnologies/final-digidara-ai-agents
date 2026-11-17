"""Settings endpoints: preferences, profile, sign-ins, two-step verification
and usage over a chosen date range."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func

from app import db
from app.account import preferences, sign_ins, two_step
from app.auth import service as auth_service
from app.auth.security import get_current_session, get_current_user_id, verify_password
from app.billing.plans import points_for_tokens
from app.models import TokenUsageEvent, User
from app.rate_limit import allow_account_attempt, limiter

router = APIRouter(prefix="/account", tags=["account"])

_PASSWORD_RATE_LIMIT = "5/minute"
_SEND_CODE_RATE_LIMIT = "5/hour"
_MAX_RANGE_DAYS = 366


class ProfileUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    mobile: str | None = Field(default=None, max_length=32)


class PasswordConfirm(BaseModel):
    password: str = Field(min_length=1, max_length=255)


class CodeConfirm(BaseModel):
    code: str = Field(min_length=1, max_length=12)


def _user(user_id: str) -> User:
    user = auth_service.get_by_id(user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "This account no longer exists.")
    return user


def _two_step_error(exc: two_step.TwoStepError) -> HTTPException:
    return HTTPException(exc.status_code, exc.message)


@router.get("/preferences")
def get_preferences(user_id: str = Depends(get_current_user_id)) -> dict:
    return preferences.get(user_id)


@router.put("/preferences")
def put_preferences(patch: dict, user_id: str = Depends(get_current_user_id)) -> dict:
    """Any part of the preferences document; the rest is kept."""
    return preferences.update(user_id, patch)


def normalize_mobile(value: str | None) -> str | None:
    """Optional +, then 7-15 digits (spaces, dashes, dots and brackets allowed);
    the same rule as the frontend's profilePrefs.normalizeMobile."""
    if value is None or not value.strip():
        return None
    cleaned = "".join(ch for ch in value.strip() if ch not in " -().")
    digits = cleaned[1:] if cleaned.startswith("+") else cleaned
    if not digits.isdigit() or not 7 <= len(digits) <= 15:
        raise HTTPException(422, "Please enter a valid mobile number.")
    return cleaned


@router.put("/profile")
def update_profile(req: ProfileUpdate, user_id: str = Depends(get_current_user_id)) -> dict:
    name = " ".join(req.name.split())
    if not name:
        raise HTTPException(422, "Please enter your name.")
    mobile = normalize_mobile(req.mobile)
    session = db.get_session()
    try:
        user = session.get(User, user_id)
        if user is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "This account no longer exists.")
        user.name = name
        user.mobile = mobile
        session.commit()
        return {"name": user.name, "mobile": user.mobile}
    finally:
        session.close()


@router.get("/sign-ins")
def list_sign_ins(current: tuple[str, str | None] = Depends(get_current_session)) -> dict:
    user_id, session_id = current
    return {"sign_ins": sign_ins.list_for(user_id, session_id)}


@router.delete("/sign-ins/{sign_in_id}")
def revoke_sign_in(sign_in_id: str, current: tuple[str, str | None] = Depends(get_current_session)) -> dict:
    user_id, _ = current
    if not sign_ins.revoke(user_id, sign_in_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "That sign-in was not found.")
    return {"revoked": True}


@router.post("/sign-ins/sign-out-others")
def sign_out_others(current: tuple[str, str | None] = Depends(get_current_session)) -> dict:
    user_id, session_id = current
    try:
        token = sign_ins.sign_out_others(user_id, session_id)
    except LookupError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "This account no longer exists.") from exc
    return {"access_token": token}


@router.get("/two-step")
def two_step_status(user_id: str = Depends(get_current_user_id)) -> dict:
    user = _user(user_id)
    return {
        "enabled": two_step.is_enabled(user_id),
        "available": two_step.available(),
        # Google-only accounts never sign in with a password, so there is nothing to protect.
        "password_account": bool(user.password_hash),
        "email": two_step.mask_email(user.email),
    }


def _check_password(user: User, password: str) -> None:
    if not allow_account_attempt("two-step-password", user.id, _PASSWORD_RATE_LIMIT):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many attempts. Please wait a minute and try again.")
    if not user.password_hash or not verify_password(password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect password.")


@router.post("/two-step/start")
@limiter.limit(_SEND_CODE_RATE_LIMIT)
def two_step_start(req: PasswordConfirm, request: Request, user_id: str = Depends(get_current_user_id)) -> dict:
    """Step 1 of turning it on: confirm the password, then email a code to
    prove the codes arrive."""
    user = _user(user_id)
    if not two_step.available():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Email is not available right now, so two-step verification can't be turned on.")
    _check_password(user, req.password)
    try:
        two_step.send_code(user_id, reason="verification")
    except two_step.TwoStepError as exc:
        raise _two_step_error(exc) from exc
    return {"message": f"We've sent a 6-digit code to {two_step.mask_email(user.email)}."}


@router.post("/two-step/enable")
def two_step_enable(req: CodeConfirm, user_id: str = Depends(get_current_user_id)) -> dict:
    if not allow_account_attempt("two-step-enable", user_id, "10/minute"):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many attempts. Please wait a minute and try again.")
    try:
        two_step.check_code(user_id, req.code)
    except two_step.TwoStepError as exc:
        raise _two_step_error(exc) from exc
    two_step.set_enabled(user_id, True)
    return {"enabled": True}


@router.post("/two-step/disable")
def two_step_disable(req: PasswordConfirm, user_id: str = Depends(get_current_user_id)) -> dict:
    _check_password(_user(user_id), req.password)
    two_step.set_enabled(user_id, False)
    return {"enabled": False}


def _parse_day(value: str, field: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(422, f"{field} must be a date like 2026-11-01.") from exc


@router.get("/usage")
def usage_range(
    start: str = Query(..., description="First day, YYYY-MM-DD, in the user's time zone"),
    end: str = Query(..., description="Last day (included), YYYY-MM-DD"),
    offset_minutes: int = Query(0, ge=-14 * 60, le=14 * 60),
    user_id: str = Depends(get_current_user_id),
) -> dict:
    """Billed usage between two days (both included), per agent and per day,
    with every charge for the CSV export."""
    user = _user(user_id)
    first, last = _parse_day(start, "start"), _parse_day(end, "end")
    if last < first:
        raise HTTPException(422, "The end date is before the start date.")
    if (last - first).days >= _MAX_RANGE_DAYS:
        raise HTTPException(422, "Please choose at most one year.")
    offset = timedelta(minutes=offset_minutes)
    since = datetime.combine(first, datetime.min.time()) - offset
    until = datetime.combine(last + timedelta(days=1), datetime.min.time()) - offset
    session = db.get_session()
    try:
        events = (session.query(TokenUsageEvent)
                  .filter(TokenUsageEvent.user_id == user_id, TokenUsageEvent.created_at >= since,
                          TokenUsageEvent.created_at < until)
                  .order_by(TokenUsageEvent.created_at.desc()).all())
    finally:
        session.close()
    rate = user.tokens_per_point
    agents: dict[str, dict] = {}
    days: dict[str, dict] = {}
    for event in events:
        agent = agents.setdefault(event.agent_name, {"agent_name": event.agent_name, "tokens": 0, "requests": 0})
        agent["tokens"] += int(event.tokens)
        agent["requests"] += 1
        day = (event.created_at + offset).date().isoformat()
        bucket = days.setdefault(day, {"day": day, "tokens": 0, "requests": 0})
        bucket["tokens"] += int(event.tokens)
        bucket["requests"] += 1
    for row in (*agents.values(), *days.values()):
        row["points"] = points_for_tokens(row["tokens"], rate)
    total = sum(row["tokens"] for row in agents.values())
    return {
        "start": first.isoformat(),
        "end": last.isoformat(),
        "tokens_used": total,
        "points_used": points_for_tokens(total, rate),
        "requests": len(events),
        "agents": sorted(agents.values(), key=lambda row: row["tokens"], reverse=True),
        "days": sorted(days.values(), key=lambda row: row["day"]),
        "events": [{
            "at": event.created_at.isoformat() + "Z",
            "agent_name": event.agent_name,
            "action": event.action,
            "tokens": int(event.tokens),
            "points": points_for_tokens(int(event.tokens), rate),
        } for event in events],
    }


def export_data(user_id: str) -> dict:
    """For the DPDP data download (auth/service.py:export_user_data)."""
    return {
        "preferences": preferences.get(user_id),
        "sign_ins": sign_ins.export(user_id),
        "two_step_enabled": two_step.is_enabled(user_id),
    }


def purge(user_id: str) -> None:
    preferences.purge(user_id)
    sign_ins.purge(user_id)
    two_step.purge(user_id)
