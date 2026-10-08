"""Job readiness: one score per learner, combined from every agent over A2A.

Each scored agent answers the `get_student_summary` skill with the shared
digidara.student_summary.v1 shape (see summarize_reply). The overall score
is the weighted sum over ALL areas, so an area the learner has not tried yet
counts as 0 -- an untested skill is not job-ready -- and `coverage` says how
many areas have been assessed. An agent that is down, or that does not serve
the skill yet, is reported as unavailable instead of failing the whole score.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

from app import db
from app.a2a import client as a2a_client
from app.learner import levels as level_rules
from app.learner import service as learner_service
from app.models import ReadinessSnapshot

logger = logging.getLogger("orchestrator.readiness")

SUMMARY_SCHEMA = "digidara.student_summary.v1"
CALLER = "readiness"
# A fresh snapshot is reused instead of asking every agent again.
SNAPSHOT_MAX_AGE = timedelta(minutes=10)
HISTORY_LIMIT = 30

# (registry agent, area label, weight). Weights add up to 100.
AREAS: tuple[tuple[str, str, int], ...] = (
    ("codeforge_agent", "Coding", 25),
    ("mock_interview_agent", "Interview", 20),
    ("aptitude_agent", "Aptitude", 15),
    ("communication_agent", "Communication", 15),
    ("resume_builder_agent", "Resume", 10),
    ("capstone_project_agent", "Projects", 10),
    ("certificate_agent", "Certification", 5),
)
TOTAL_WEIGHT = sum(weight for _, _, weight in AREAS)

BANDS: tuple[tuple[float, str, str], ...] = (
    (80, "job_ready", "Job ready"),
    (60, "almost_ready", "Almost ready"),
    (40, "developing", "Developing"),
    (0, "not_ready", "Not ready yet"),
)
BAND_LABELS = {key: label for _, key, label in BANDS} | {"not_started": "Not started"}


def band_for(overall: float | None, assessed: int) -> str:
    if not assessed or overall is None:
        return "not_started"
    return next(key for threshold, key, _ in BANDS if overall >= threshold)


def _clamp_score(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return round(min(100.0, max(0.0, float(value))), 1)


def _strings(value: Any, limit: int = 5) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item)[:160] for item in value if isinstance(item, (str, int, float))][:limit]


def summarize_reply(data: Any) -> dict:
    """Validate one agent's student summary; anything unexpected is dropped."""
    if not isinstance(data, dict):
        return {"score": None, "activity_count": 0, "last_activity_at": None, "strengths": [], "gaps": [], "metrics": {}}
    activity = data.get("activity_count")
    metrics = data.get("metrics") if isinstance(data.get("metrics"), dict) else {}
    return {
        "score": _clamp_score(data.get("score")),
        "activity_count": activity if isinstance(activity, int) and activity >= 0 else 0,
        "last_activity_at": data.get("last_activity_at") if isinstance(data.get("last_activity_at"), str) else None,
        "strengths": _strings(data.get("strengths")),
        "gaps": _strings(data.get("gaps")),
        "metrics": {str(k)[:60]: v for k, v in list(metrics.items())[:20] if isinstance(v, (str, int, float, bool)) or v is None},
    }


async def _area(agent_name: str, label: str, weight: int, user, levels: dict) -> dict:
    result = await a2a_client.send(agent_name, "get_student_summary", {"email": user.email}, user, CALLER)
    level = levels.get(agent_name, {}).get("level", level_rules.DEFAULT_LEVEL)
    base = {"agent_name": agent_name, "label": label, "weight": weight, "level": level}
    if result.state != "completed":
        return {**base, "status": "unavailable", "reason": result.error or "No summary from this agent yet.",
                "score": None, "activity_count": 0, "last_activity_at": None, "strengths": [], "gaps": [],
                "metrics": {}, "suggested_level": None}
    summary = summarize_reply(result.data)
    status = "assessed" if summary["score"] is not None else "not_started"
    return {**base, "status": status, **summary, "suggested_level": level_rules.suggested_level(summary["score"])}


def _next_steps(areas: list[dict]) -> list[str]:
    """Up to three things to do next, weakest weighted areas first."""
    steps: list[str] = []
    for area in sorted(areas, key=lambda a: ((a["score"] or 0) - 100) * a["weight"]):
        if area["status"] == "not_started":
            steps.append(f"Start {area['label']}: no {area['label'].lower()} activity yet.")
        elif area["status"] == "assessed" and (area["score"] or 0) < 80:
            gap = area["gaps"][0] if area["gaps"] else None
            steps.append(f"Improve {area['label']} ({area['score']:.0f}/100)" + (f": {gap}" if gap else "."))
        if len(steps) == 3:
            break
    return steps


async def compute(user) -> dict:
    levels = learner_service.get_levels(user.id)
    areas = list(await asyncio.gather(*(_area(name, label, weight, user, levels) for name, label, weight in AREAS)))
    assessed = [a for a in areas if a["status"] == "assessed"]
    overall = round(sum((a["score"] or 0) * a["weight"] for a in assessed) / TOTAL_WEIGHT, 1) if assessed else None
    band = band_for(overall, len(assessed))
    result = {
        "overall": overall,
        "band": band,
        "band_label": BAND_LABELS[band],
        "coverage": {"assessed": len(assessed), "total": len(AREAS)},
        "areas": areas,
        "next_steps": _next_steps(areas),
        "profile": learner_service.get_profile(user.id),
        "computed_at": datetime.utcnow().isoformat(),
    }
    _store(user.id, result)
    return result


def _store(user_id: str, result: dict) -> None:
    session = db.get_session()
    try:
        session.add(ReadinessSnapshot(
            user_id=user_id, overall=result["overall"], band=result["band"],
            areas={"areas": result["areas"], "next_steps": result["next_steps"]},
        ))
        session.commit()
    finally:
        session.close()


def area_scores(snapshot: ReadinessSnapshot) -> dict[str, dict]:
    """agent_name -> {score, status, level} from a stored snapshot."""
    stored = (snapshot.areas or {}).get("areas") or []
    return {
        a["agent_name"]: {"score": a.get("score"), "status": a.get("status"), "level": a.get("level")}
        for a in stored if isinstance(a, dict) and a.get("agent_name")
    }


def latest(user_id: str) -> ReadinessSnapshot | None:
    session = db.get_session()
    try:
        return (
            session.query(ReadinessSnapshot).filter_by(user_id=user_id)
            .order_by(ReadinessSnapshot.computed_at.desc()).first()
        )
    finally:
        session.close()


def latest_for(user_ids: list[str]) -> dict[str, ReadinessSnapshot]:
    """Each user's most recent snapshot, for the organization dashboard."""
    if not user_ids:
        return {}
    session = db.get_session()
    try:
        rows = (
            session.query(ReadinessSnapshot).filter(ReadinessSnapshot.user_id.in_(user_ids))
            .order_by(ReadinessSnapshot.computed_at.desc()).all()
        )
    finally:
        session.close()
    result: dict[str, ReadinessSnapshot] = {}
    for row in rows:
        result.setdefault(row.user_id, row)
    return result


def history(user_id: str) -> list[dict]:
    session = db.get_session()
    try:
        rows = (
            session.query(ReadinessSnapshot).filter_by(user_id=user_id)
            .order_by(ReadinessSnapshot.computed_at.desc()).limit(HISTORY_LIMIT).all()
        )
    finally:
        session.close()
    return [
        {"overall": row.overall, "band": row.band, "computed_at": row.computed_at.isoformat()}
        for row in reversed(rows)
    ]


async def get(user, refresh: bool = False) -> dict:
    """The readiness result, recomputed when asked or when the last one is old."""
    snapshot = latest(user.id)
    if refresh or snapshot is None or datetime.utcnow() - snapshot.computed_at > SNAPSHOT_MAX_AGE:
        return await compute(user)
    stored = snapshot.areas or {}
    if not isinstance(stored.get("areas"), list):
        return await compute(user)
    levels = learner_service.get_levels(user.id)
    areas = [
        {**area, "level": levels.get(area["agent_name"], {}).get("level", area.get("level"))}
        for area in stored["areas"] if isinstance(area, dict) and area.get("agent_name")
    ]
    return {
        "overall": snapshot.overall, "band": snapshot.band,
        "band_label": BAND_LABELS.get(snapshot.band, snapshot.band),
        "coverage": {"assessed": sum(1 for a in areas if a.get("status") == "assessed"), "total": len(AREAS)},
        "areas": areas, "next_steps": stored.get("next_steps") or [],
        "profile": learner_service.get_profile(user.id),
        "computed_at": snapshot.computed_at.isoformat(), "cached": True,
    }


async def skill(action: str, user) -> dict:
    """The readiness pseudo-agent's A2A skills, for other agents to call."""
    if action == "get_readiness":
        return await get(user)
    if action == "get_learner_profile":
        return {"profile": learner_service.get_profile(user.id), "levels": learner_service.get_levels(user.id)}
    from app.a2a.protocol import INVALID_PARAMS, RpcError

    raise RpcError(INVALID_PARAMS, f"Unknown readiness skill {action!r}. Use get_readiness or get_learner_profile.")


def purge(user_id: str) -> None:
    session = db.get_session()
    try:
        session.query(ReadinessSnapshot).filter_by(user_id=user_id).delete()
        session.commit()
    finally:
        session.close()
