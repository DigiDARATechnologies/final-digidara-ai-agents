"""Small repairs Boss can make for the signed-in learner, from a fixed list:
re-check their job readiness, continue a stalled interview or finish its report,
exit an interview, switch to a level that is already open, cancel their own chat
links, and report a problem to the SkillDARA team.

The model only asks for a repair (assist._actions keeps tags from a fixed list).
Whether it runs is decided here, in code: each repair acts for the verified user
only, checks the real state first, and the ones that end or change something
need the learner's own words, so instructions hidden in a screenshot or a chat
line cannot trigger them. Nothing here can change marks, points, certificates,
payments, passwords or anyone else's data.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta

from fastapi import HTTPException

from app import db
from app.gateway import routes as gateway
from app.learner import levels as level_rules
from app.learner import service as learner_service
from app.links import service as links_service
from app.models import BossIssueReport
from app.readiness import service as readiness_service

logger = logging.getLogger("orchestrator.boss.repairs")

INTERVIEW_AGENT = "mock_interview_agent"
CALLER = "boss_repair"
# Agents whose level can be switched here: the scored ones with levels.
LEVEL_AGENTS = {name: label for name, label, _ in readiness_service.AREAS if name not in level_rules.UNLEVELED_AGENTS}
REPORT_CATEGORIES = ("interview", "score", "level", "link", "other")
REPORTS_PER_DAY = 5
MAX_REPORT_CHARS = 500

_YES = re.compile(r"^\s*(yes|yeah|yep|ok|okay|sure|confirm|please do|do it|go ahead)\b", re.IGNORECASE)
_REPORT_WORDS = re.compile(r"\b(report|complain|complaint|support|tell (?:the|your) team)\b", re.IGNORECASE)


def _last_turn(history: list[dict], role: str) -> str:
    return next((str(turn.get("content") or "") for turn in reversed(history) if turn.get("role") == role), "")


def _agreed(message: str, history: list[dict], topic: str) -> bool:
    """The learner said yes to Boss's last message, and that message was about `topic`."""
    return bool(_YES.match(message)) and topic.lower() in _last_turn(history, "assistant").lower()


def _result(name: str, ok: bool, text: str, **extra) -> dict:
    return {"type": "repair", "name": name, "ok": ok, "text": text, **extra}


async def _interview_call(user, action: str, payload: dict | None = None) -> tuple[int, dict]:
    """One Mock Interview action through the gateway, for this verified user:
    the same signing, identity and billing as the browser's own calls."""
    try:
        response = await gateway.invoke_json(INTERVIEW_AGENT, action, payload or {}, user, CALLER)
    except HTTPException as exc:
        return exc.status_code, {"error": str(exc.detail)}
    try:
        return response.status_code, json.loads(response.body or b"{}")
    except ValueError:
        return response.status_code, {}


async def interview_state(user) -> dict:
    """Where the learner's interview stands. `state`: none, question (waiting
    for an answer), stalled (its next question was never issued) or
    awaiting_report (every answer is in, the report is not made yet)."""
    status, session = await _interview_call(user, "ensure_session")
    token = session.get("sessionToken")
    if status != 200 or not token:
        return {"state": "unknown"}
    status, active = await _interview_call(user, "active_interview", {"sessionToken": token})
    state = "none"
    if active.get("active"):
        state = "question"
    elif active.get("awaiting_report"):
        state = "awaiting_report"
    elif active.get("needs_next_question"):
        state = "stalled"
    elif status not in (200, 409):
        state = "unknown"
    return {**active, "state": state, "token": token}


def _start_body(active: dict) -> dict:
    """The stalled interview's own settings: starting with them resumes it."""
    body = {key: active.get(key) for key in ("round_type", "interview_mode", "subject", "role_name", "difficulty",
                                             "resolved_subjects") if active.get(key) is not None}
    if isinstance(body.get("resolved_subjects"), str):
        body["resolved_subjects"] = json.loads(body["resolved_subjects"])
    # A resumed interview keeps its own length; this only has to be a valid choice
    # (one shortened by the daily limit may be stored with another number).
    body["num_questions"] = active.get("num_questions") if active.get("num_questions") in (5, 10, 15) else 5
    return body


async def _continue_interview(user) -> dict:
    name = "interview_continue"
    current = await interview_state(user)
    if current["state"] == "question":
        return _result(name, True, "Your interview is waiting for your answer. Opening it now.", open="mock-interview")
    if current["state"] != "stalled":
        return _result(name, False, "There is no stalled interview to continue.")
    status, started = await _interview_call(user, "start_interview", {**_start_body(current), "sessionToken": current["token"]})
    if status != 200 or not started.get("question"):
        return _result(name, False, "I could not prepare your next question just now. Please try again in a minute.")
    return _result(name, True, "Your next question is ready. Opening your interview now.", open="mock-interview")


async def _finish_report(user) -> dict:
    name = "interview_report"
    current = await interview_state(user)
    if current["state"] != "awaiting_report":
        return _result(name, False, "No finished interview is waiting for its report.")
    status, _ = await _interview_call(user, "end_interview", {"interview_id": current["interview_id"], "sessionToken": current["token"]})
    if status != 200:
        return _result(name, False, "The report could not be made just now. Your answers are safe; please try again in a minute.")
    return _result(name, True, "Your interview report is ready. You can see it in your interview history.")


async def _exit_interview(user, message: str, history: list[dict]) -> dict:
    name = "interview_exit"
    if not _agreed(message, history, "exit"):
        logger.warning("boss repair refused, the learner did not confirm: %s user=%s", name, user.id)
        return _result(name, False, "Nothing was changed. Say yes when I ask, and I will exit the interview.")
    current = await interview_state(user)
    if current["state"] not in ("question", "stalled", "awaiting_report"):
        return _result(name, False, "You have no open interview to exit.")
    status, _ = await _interview_call(user, "exit_interview", {"interview_id": current["interview_id"], "sessionToken": current["token"]})
    if status != 200:
        return _result(name, False, "I could not exit the interview just now. Please try again in a minute.")
    return _result(name, True, "Your interview is closed. Your answers are saved and you can start a new one.")


async def _refresh_readiness(user) -> dict:
    name = "readiness"
    result = await readiness_service.get(user, refresh=True)
    overall = result.get("overall")
    return _result(name, True, "Your job readiness is checked again." if overall is None
                   else f"Your job readiness is checked again: {round(overall)}/100.")


def _switch_level(user, agent: str, level: str, message: str, history: list[dict]) -> dict:
    name = "level"
    label = level_rules.LEVEL_LABELS[level]
    if level not in message.lower() and not _agreed(message, history, level):
        logger.warning("boss repair refused, the learner did not ask: %s user=%s", name, user.id)
        return _result(name, False, f"Nothing was changed. Tell me if you want to switch to {label}.")
    current = learner_service.get_levels(user.id).get(agent) or {}
    if current.get("source") == "organization":
        return _result(name, False, "Your organization set this level, so please ask them to change it.")
    if level not in readiness_service.open_levels_for(user.id, agent):
        return _result(name, False, f"{label} is not open yet in {LEVEL_AGENTS[agent]}.")
    learner_service.set_level(user.id, agent, level, "self")
    return _result(name, True, f"Your {LEVEL_AGENTS[agent]} level is now {label}. Your points do not change.")


def _report(user, category: str, agent_id: str, message: str, history: list[dict]) -> dict:
    name = "report"
    if not _REPORT_WORDS.search(message) and not _agreed(message, history, "team"):
        logger.warning("boss repair refused, the learner did not ask: %s user=%s", name, user.id)
        return _result(name, False, "Nothing was sent. Tell me if you want this reported to the SkillDARA team.")
    # After a plain "yes", the problem itself is in what they said before it.
    words = _last_turn(history, "user") if _YES.match(message) else message
    session = db.get_session()
    try:
        since = datetime.utcnow() - timedelta(days=1)
        if session.query(BossIssueReport).filter(BossIssueReport.user_id == user.id, BossIssueReport.created_at >= since).count() >= REPORTS_PER_DAY:
            return _result(name, False, "You have sent several reports today. The team will look at those first.")
        session.add(BossIssueReport(user_id=user.id, category=category, agent_id=agent_id[:60], message=words[:MAX_REPORT_CHARS]))
        session.commit()
    finally:
        session.close()
    return _result(name, True, "I sent this to the SkillDARA team.")


def _cancel_links(user, chat_id: str) -> dict:
    removed = links_service.remove_chat_links(user.id, chat_id)
    return _result("unshare", True, "The links to that chat are cancelled. They no longer open." if removed
                   else "That chat has no links to cancel.")


async def run(user, action: dict, message: str, history: list[dict], agent_id: str = "") -> dict:
    """One repair Boss asked for (see assist._actions), as the event for the browser."""
    kind = action.get("type")
    name = str(action.get("name") or kind)
    try:
        if name == "readiness":
            return await _refresh_readiness(user)
        if name == "interview_continue":
            return await _continue_interview(user)
        if name == "interview_report":
            return await _finish_report(user)
        if name == "interview_exit":
            return await _exit_interview(user, message, history)
        if kind == "level":
            return _switch_level(user, action["agent"], action["level"], message, history)
        if kind == "report":
            return _report(user, action["category"], agent_id, message, history)
        if kind == "unshare":
            return _cancel_links(user, action["chat_id"])
    except Exception:
        logger.exception("boss repair failed: %s user=%s", name, user.id)
    return _result(name, False, "I could not do that just now. Please try again in a minute.")
