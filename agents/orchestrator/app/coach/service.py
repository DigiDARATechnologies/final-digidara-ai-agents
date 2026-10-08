"""AI career coach: a personal plan, orchestrated across the agents over A2A.

1. Readiness asks every agent for its student summary (A2A).
2. The learner's profile and shared memory add the goal and what they said.
3. An LLM turns that into a few weeks of concrete tasks, each pointing at the
   agent and level that does it, in English or Tamil.
The plan is stored, and its headline becomes a shared memory so every agent
knows what the learner is working on this week.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta

from fastapi.concurrency import run_in_threadpool

from app import db
from app.auth import service as auth_service
from app.learner import levels as level_rules
from app.learner import service as learner_service
from app.llm.client import call_text
from app.memory import service as memory_service
from app.models import CareerPlan
from app.readiness import service as readiness_service

logger = logging.getLogger("orchestrator.coach")

WEEKS = 4
LANGUAGES = {"en": "English", "ta": "Tamil (natural, friendly spoken-style Tamil; keep agent names and technical words in English)"}

_SYSTEM = """You are DigiDARA's friendly career coach for students in India.
Write a practical, encouraging job-readiness plan from the data given.
Return JSON only:
{"headline": str, "summary": str, "weeks": [{"week": int, "focus": str,
 "tasks": [{"agent_name": str, "title": str, "why": str, "level": str}]}],
 "encouragement": str}
Rules: exactly {weeks} weeks; 2-4 tasks per week; agent_name must be one of
the given agent ids; level is one of beginner, medium, hard, professional and
should step up only when the learner's scores support it; spend the most
time on the weakest heavily-weighted areas; mention the target role; never
invent scores or facts; keep every string short and friendly. Write all
strings in {language}."""


# One LLM turn over the learner's readiness, charged as tokens like an agent call.
PLAN_TOKEN_COST = int(os.environ.get("CAREER_PLAN_TOKEN_COST", "1500"))
# A plan asked for again this soon is returned as it is, not rewritten.
PLAN_COOLDOWN = timedelta(seconds=60)


class PlanError(RuntimeError):
    pass


class NoPoints(PlanError):
    pass


def _parse(text: str) -> dict:
    candidate = text.strip()
    if candidate.startswith("```"):
        candidate = candidate.split("\n", 1)[1] if "\n" in candidate else ""
        candidate = candidate.rsplit("```", 1)[0]
    try:
        plan = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise PlanError("The coach did not return a valid plan.") from exc
    if not isinstance(plan, dict) or not isinstance(plan.get("weeks"), list):
        raise PlanError("The coach did not return a valid plan.")
    weeks = []
    for index, week in enumerate(plan["weeks"][:WEEKS], 1):
        if not isinstance(week, dict):
            continue
        tasks = []
        for task in (week.get("tasks") or [])[:4]:
            if not isinstance(task, dict) or task.get("agent_name") not in level_rules.LEVELED_AGENTS:
                continue
            tasks.append({
                "agent_name": task["agent_name"],
                "agent_label": level_rules.LEVELED_AGENTS[task["agent_name"]],
                "title": str(task.get("title") or "")[:160],
                "why": str(task.get("why") or "")[:240],
                "level": level_rules.normalize(task.get("level")),
            })
        weeks.append({"week": index, "focus": str(week.get("focus") or "")[:160], "tasks": tasks})
    return {
        "headline": str(plan.get("headline") or "")[:160],
        "summary": str(plan.get("summary") or "")[:600],
        "weeks": weeks,
        "encouragement": str(plan.get("encouragement") or "")[:300],
    }


def _prompt(readiness: dict, memories: list[dict]) -> str:
    profile = readiness["profile"]
    areas = [
        {"agent": a["agent_name"], "area": a["label"], "weight_percent": a["weight"], "status": a["status"],
         "score": a["score"], "current_level": a["level"], "strengths": a["strengths"][:2], "gaps": a["gaps"][:3]}
        for a in readiness["areas"]
    ]
    return json.dumps({
        "target_role": profile.get("target_role"), "degree": profile.get("degree"),
        "skills": profile.get("skills"), "experience": profile.get("experience"),
        "overall_readiness": readiness["overall"], "band": readiness["band_label"],
        "areas": areas, "agent_ids": list(level_rules.LEVELED_AGENTS),
        "learner_memory": [m["text"] for m in memories][:12],
    }, ensure_ascii=False)


def get(user_id: str) -> dict | None:
    session = db.get_session()
    try:
        row = session.get(CareerPlan, user_id)
        if row is None:
            return None
        return {**row.plan, "language": row.language, "created_at": row.created_at.isoformat()}
    finally:
        session.close()


async def generate(user, language: str = "en") -> dict:
    language = language if language in LANGUAGES else "en"
    current = get(user.id)
    if current and current.get("language") == language and             datetime.utcnow() - datetime.fromisoformat(current["created_at"]) < PLAN_COOLDOWN:
        return current
    if PLAN_TOKEN_COST and user.token_balance <= 0:
        raise NoPoints("Not enough points. Please top up to continue.")
    readiness = await readiness_service.get(user)
    memories = memory_service.list_for(user.id)
    system = _SYSTEM.replace("{weeks}", str(WEEKS)).replace("{language}", LANGUAGES[language])
    try:
        text = await run_in_threadpool(call_text, system, _prompt(readiness, memories), 0.4)
    except Exception as exc:  # provider failures must not leak detail
        logger.exception("career plan generation failed")
        raise PlanError("The coach could not write a plan right now. Please try again.") from exc
    plan = _parse(text)
    session = db.get_session()
    try:
        row = session.get(CareerPlan, user.id) or CareerPlan(user_id=user.id)
        row.plan, row.language, row.created_at = plan, language, datetime.utcnow()
        session.merge(row)
        session.commit()
    finally:
        session.close()
    if PLAN_TOKEN_COST:
        auth_service.settle_tokens(user.id, PLAN_TOKEN_COST, "career_coach", "create_plan")
    if plan["weeks"]:
        first = plan["weeks"][0]
        memory_service.add(user.id, f"This week's plan: {first['focus']}", "goal", "coach", None, 4)
    return {**plan, "language": language, "created_at": datetime.utcnow().isoformat(),
            "readiness": {"overall": readiness["overall"], "band_label": readiness["band_label"]}}


async def skill(action: str, payload: dict, user) -> dict:
    if action == "get_plan":
        return {"plan": get(user.id)}
    if action == "create_plan":
        return {"plan": await generate(user, str(payload.get("language") or "en"))}
    from app.a2a.protocol import INVALID_PARAMS, RpcError

    raise RpcError(INVALID_PARAMS, f"Unknown coach skill {action!r}. Use get_plan or create_plan.")


def purge(user_id: str) -> None:
    session = db.get_session()
    try:
        session.query(CareerPlan).filter_by(user_id=user_id).delete()
        session.commit()
    finally:
        session.close()
