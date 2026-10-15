"""Job readiness: one score per learner, combined from every agent over A2A.

Scores count completed levels only (the Resume Builder has no levels: its
area score is its best ATS score). Each of the four levels is worth
LEVEL_POINTS (25), so an area with Beginner completed scores 25, Medium 50,
Hard 75 and Professional 100; progress inside a level is shown on its own
(level_progress) and adds nothing until the level is complete. The overall
score is the average over all seven areas, so it reaches 25 only when every
agent's Beginner is complete, 50 when every Medium is, and so on. The
agent's own result is kept as `quality_score`.

Each scored agent answers the `get_student_summary` skill with the shared
digidara.student_summary.v1 shape (see summarize_reply). An area the learner
has not tried yet counts as 0 -- an untested skill is not job-ready -- and `coverage` says how
many areas have been assessed. An agent that is down, or that does not serve
the skill yet, is reported as unavailable instead of failing the whole score.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from app import db
from app.a2a import client as a2a_client
from app.learner import levels as level_rules
from app.learner import service as learner_service
from app.memory import service as memory_service
from app.models import ReadinessSnapshot
from sqlalchemy import or_

logger = logging.getLogger("orchestrator.readiness")

SUMMARY_SCHEMA = "digidara.student_summary.v1"
CALLER = "readiness"
# A fresh snapshot is reused instead of asking every agent again.
SNAPSHOT_MAX_AGE = timedelta(minutes=10)
# A refresh asked for within this long of the last one reuses it, so opening
# the readiness page repeatedly does not ask every agent each time.
REFRESH_MIN_AGE = timedelta(seconds=15)
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
LEVEL_POINTS = 100 / len(level_rules.LEVELS)
# Agents whose summary measures progress at the learner's own level; they get
# the level's difficulty in the request. Others fall back to their score.
LEVEL_PROGRESS_AGENTS = frozenset({"codeforge_agent"})

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


def _text(value: Any, limit: int) -> str:
    return " ".join(str(value).split())[:limit] if isinstance(value, (str, int, float)) else ""


def _resume_block(value: Any) -> dict:
    """An agent's optional resume facts, cut down to plain short text:
    skills, projects, certifications and achievements."""
    if not isinstance(value, dict):
        return {}
    def items(key: str, fields: dict[str, int], required: str, limit: int) -> list[dict]:
        rows = value.get(key) if isinstance(value.get(key), list) else []
        result = []
        for row in rows[:limit]:
            if not isinstance(row, dict) or not _text(row.get(required), 200):
                continue
            item = {field: _text(row.get(field), size) for field, size in fields.items() if _text(row.get(field), size)}
            if isinstance(row.get("skills"), list):
                item["skills"] = _strings(row["skills"], 8)
            if isinstance(row.get("score"), (int, float)) and not isinstance(row.get("score"), bool):
                item["score"] = _clamp_score(row["score"])
            result.append(item)
        return result
    block = {
        "skills": [_text(s, 60) for s in _strings(value.get("skills"), 12) if _text(s, 60)],
        "projects": items("projects", {"title": 160, "description": 400}, "title", 4),
        "certifications": items("certifications", {"name": 200, "issuer": 120, "date": 10}, "name", 6),
        "achievements": items("achievements", {"title": 160, "description": 300}, "title", 4),
    }
    return {key: rows for key, rows in block.items() if rows}


def summarize_reply(data: Any) -> dict:
    """Validate one agent's student summary; anything unexpected is dropped."""
    if not isinstance(data, dict):
        return {"score": None, "activity_count": 0, "last_activity_at": None, "strengths": [], "gaps": [], "metrics": {},
                "resume": {}, "level_scores": {}, "recent": []}
    activity = data.get("activity_count")
    metrics = data.get("metrics") if isinstance(data.get("metrics"), dict) else {}
    return {
        "score": _clamp_score(data.get("score")),
        "activity_count": activity if isinstance(activity, int) and activity >= 0 else 0,
        "last_activity_at": data.get("last_activity_at") if isinstance(data.get("last_activity_at"), str) else None,
        "strengths": _strings(data.get("strengths")),
        "gaps": _strings(data.get("gaps")),
        "metrics": {str(k)[:60]: v for k, v in list(metrics.items())[:20] if isinstance(v, (str, int, float, bool)) or v is None},
        "resume": _resume_block(data.get("resume")),
        "level_scores": _level_scores(data.get("level_scores")),
        "recent": _recent(data.get("recent")),
    }


RECENT_LIMIT = 10


def _recent(value: Any) -> list[dict]:
    """An agent's latest dated activities (newest first), e.g. each aptitude
    test with its date and score, so the learner can ask Boss about them."""
    if not isinstance(value, list):
        return []
    rows = []
    for row in value[:RECENT_LIMIT]:
        if not isinstance(row, dict) or not _text(row.get("date"), 32):
            continue
        item: dict[str, Any] = {"date": _text(row.get("date"), 32)}
        for field, size in (("title", 120), ("level", 20)):
            if _text(row.get(field), size):
                item[field] = _text(row.get(field), size)
        score = _clamp_score(row.get("score"))
        if score is not None:
            item["score"] = score
        rows.append(item)
    return rows


def _level_scores(value: Any) -> dict[str, float]:
    """An agent's progress (0-100) at easy/medium/hard (and professional when it
    measures that level separately), as one per learner level."""
    if not isinstance(value, dict):
        return {}
    by_difficulty = {key: _clamp_score(value.get(key)) for key in ("easy", "medium", "hard")}
    if all(score is None for score in by_difficulty.values()):
        return {}
    scores = {level: by_difficulty[difficulty] or 0.0 for level, difficulty in level_rules.LEVEL_DIFFICULTY.items()}
    # An agent with its own Professional measure (Coding: passed Professional
    # assessments) reports it; otherwise Professional keeps the Hard results.
    professional = _clamp_score(value.get("professional"))
    if professional is not None:
        scores["professional"] = professional
    return scores


async def _area(agent_name: str, label: str, weight: int, user, levels: dict, periods: list[dict] | None = None) -> dict:
    level = levels.get(agent_name, {}).get("level", level_rules.DEFAULT_LEVEL)
    request: dict[str, Any] = {"email": user.email}
    if periods:
        # Only activity done while the current target role was the goal counts.
        request["periods"] = periods
    if agent_name in LEVEL_PROGRESS_AGENTS:
        request["difficulty"] = level_rules.agent_difficulty(agent_name, level)
    result = await a2a_client.send(agent_name, "get_student_summary", request, user, CALLER)
    leveled = agent_name not in level_rules.UNLEVELED_AGENTS
    base = {"agent_name": agent_name, "label": label, "weight": weight, "level": level if leveled else None,
            "leveled": leveled}
    if result.state != "completed":
        return {**base, "status": "unavailable", "reason": result.error or "No summary from this agent yet.",
                "score": None, "activity_count": 0, "last_activity_at": None, "strengths": [], "gaps": [],
                "metrics": {}, "suggested_level": None, **_level_fields(level, None, "score", agent_name)}
    summary = summarize_reply(result.data)
    status = "assessed" if summary["score"] is not None else "not_started"
    if not leveled:
        return {**base, "status": status, **summary, "level_progress": None, "level_progress_basis": "score",
                "next_level": None, "can_level_up": False, "unlock_at": None, "suggested_level": None}
    measured = summary["level_scores"].get(level)
    progress, basis = (measured, "level") if measured is not None else (summary["score"], "score")
    fields = _level_fields(level, progress, basis, agent_name)
    return {**base, "status": status, **summary, **fields,
            "suggested_level": fields["next_level"] if fields["can_level_up"] else None}


def _level_fields(level: str, progress: float | None, basis: str, agent_name: str = "") -> dict:
    upcoming = level_rules.next_level(level)
    return {
        "level_progress": progress, "level_progress_basis": basis, "next_level": upcoming,
        "can_level_up": bool(upcoming) and progress is not None and progress >= level_rules.unlock_progress(agent_name),
        "unlock_at": level_rules.unlock_progress(agent_name),
    }


def _naive_utc(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return parsed.astimezone(timezone.utc).replace(tzinfo=None) if parsed.tzinfo else parsed


def _auto_promote(user, areas: list[dict], levels: dict) -> None:
    """A learner who completes their level with an agent moves up one level.
    It needs practice since the level last changed, so a full score does not
    carry them through every level at once; organization-set levels stay."""
    for area in areas:
        current = levels.get(area["agent_name"], {})
        upcoming = area.get("next_level")
        progress = area.get("level_progress")
        if area["status"] != "assessed" or not upcoming or progress is None:
            continue
        if progress < level_rules.PROMOTE_PROGRESS or current.get("source") == "organization":
            continue
        changed_at = _naive_utc(current.get("updated_at"))
        practised_at = _naive_utc(area.get("last_activity_at"))
        if changed_at and (practised_at is None or practised_at <= changed_at):
            continue
        learner_service.set_level(user.id, area["agent_name"], upcoming, "readiness")
        old = area["level"]
        measured = (area.get("level_scores") or {}).get(upcoming) if area["level_progress_basis"] == "level" else None
        area.update({"promoted_from": old, "level": upcoming, "suggested_level": None,
                     **_level_fields(upcoming, measured, area["level_progress_basis"], area["agent_name"])})
        try:
            memory_service.add(
                user.id,
                f"{area['label']}: completed {level_rules.LEVEL_LABELS[old]}, moved up to {level_rules.LEVEL_LABELS[upcoming]}",
                kind="milestone", source="readiness", agent_name=area["agent_name"],
            )
        except Exception:
            logger.warning("level milestone not remembered", exc_info=True)


def completed_levels(area: dict) -> list[str]:
    """The levels this area has completed (100% of the level done). A level
    below the current one counts as completed when the agent does not
    measure each level -- the learner moved past it."""
    if area.get("status") != "assessed" or area.get("leveled") is False:
        return []
    current = level_rules.LEVELS.index(level_rules.normalize(area.get("level")))
    measured = area.get("level_progress_basis") == "level"
    scores = area.get("level_scores") or {}
    done = []
    for name in level_rules.LEVELS[:current]:
        value = scores.get(name) if measured else None
        if not measured or (isinstance(value, (int, float)) and value >= level_rules.PROMOTE_PROGRESS):
            done.append(name)
    progress = area.get("level_progress")
    if isinstance(progress, (int, float)) and progress >= level_rules.PROMOTE_PROGRESS:
        done.append(level_rules.LEVELS[current])
    return done


def level_score(area: dict) -> float | None:
    """The area's 0-100 score: LEVEL_POINTS for each completed level; an
    area without levels scores its own result."""
    if area.get("status") != "assessed":
        return None
    if area.get("leveled") is False:
        return area.get("quality_score")
    return round(LEVEL_POINTS * len(completed_levels(area)), 1)


def overall_score(areas: list[dict]) -> float:
    """The average area score over every area (untried areas count as 0)."""
    return round(sum(a["score"] or 0 for a in areas if a.get("status") == "assessed") / len(AREAS), 1)


def level_progress(user_id: str, agent_name: str, level: str) -> float | None:
    """The learner's progress at `level` with this agent, from their latest
    readiness snapshot; None when that snapshot was taken at another level."""
    snapshot = latest(user_id)
    for area in ((snapshot.areas or {}).get("areas") or []) if snapshot else []:
        if isinstance(area, dict) and area.get("agent_name") == agent_name:
            if area.get("level") != level:
                return None
            value = area["level_progress"] if "level_progress" in area else area.get("score")
            return float(value) if isinstance(value, (int, float)) else None
    return None


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
    periods = learner_service.role_periods(user.id)
    areas = list(await asyncio.gather(*(_area(name, label, weight, user, levels, periods) for name, label, weight in AREAS)))
    try:
        _auto_promote(user, areas, levels)
    except Exception:
        logger.warning("automatic level change failed", exc_info=True)
    for area in areas:
        area["quality_score"] = area["score"]
        area["levels_completed"] = completed_levels(area)
        area["score"] = level_score(area)
    assessed = [a for a in areas if a["status"] == "assessed"]
    overall = overall_score(areas) if assessed else None
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
    try:
        memory_service.sync_readiness(user.id, areas)
    except Exception:
        logger.warning("readiness memory sync failed", exc_info=True)
    return result


def _store(user_id: str, result: dict) -> None:
    """Adds a snapshot; an unchanged result only moves the last one's time,
    so the history trend shows changes, not every page visit."""
    stored = {"areas": result["areas"], "next_steps": result["next_steps"]}
    role = learner_service.role_key(user_id)
    session = db.get_session()
    try:
        last = (
            session.query(ReadinessSnapshot).filter_by(user_id=user_id, role_key=role)
            .order_by(ReadinessSnapshot.computed_at.desc()).first()
        )
        if last is not None and last.overall == result["overall"] and last.band == result["band"] and last.areas == stored:
            last.computed_at = datetime.utcnow()
            session.commit()
            return
        session.add(ReadinessSnapshot(
            user_id=user_id, overall=result["overall"], band=result["band"],
            areas=stored, role_key=role,
        ))
        session.commit()
    finally:
        session.close()


def area_scores(snapshot: ReadinessSnapshot) -> dict[str, dict]:
    """agent_name -> {score, status, level, level_progress, level_scores} from
    a stored snapshot (level_progress is at the level the snapshot was taken)."""
    stored = (snapshot.areas or {}).get("areas") or []
    return {
        a["agent_name"]: {
            "score": a.get("score"), "status": a.get("status"), "level": a.get("level"),
            "level_progress": a.get("level_progress"), "level_scores": a.get("level_scores") or {},
            "levels_completed": a.get("levels_completed") or [], "quality_score": a.get("quality_score"),
            "leveled": a.get("leveled", True),
        }
        for a in stored if isinstance(a, dict) and a.get("agent_name")
    }


def _for_current_role(query, user_id: str):
    """Snapshots of the learner's current target role. Untagged ones are from
    before role tracks; a role change tags them with the role they were for."""
    role = learner_service.role_key(user_id)
    return query.filter(ReadinessSnapshot.user_id == user_id,
                        or_(ReadinessSnapshot.role_key == role, ReadinessSnapshot.role_key == ""))


def latest(user_id: str) -> ReadinessSnapshot | None:
    session = db.get_session()
    try:
        return (
            _for_current_role(session.query(ReadinessSnapshot), user_id)
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
            _for_current_role(session.query(ReadinessSnapshot), user_id)
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
    age = datetime.utcnow() - snapshot.computed_at if snapshot is not None else None
    levels = learner_service.get_levels(user.id)
    # A level changed after the snapshot: its progress was measured at the old level.
    level_changed = snapshot is not None and any(
        (changed := _naive_utc(level.get("updated_at"))) and changed > snapshot.computed_at for level in levels.values()
    )
    if age is None or age > SNAPSHOT_MAX_AGE or (refresh and (age > REFRESH_MIN_AGE or level_changed)):
        return await compute(user)
    stored = snapshot.areas or {}
    if not isinstance(stored.get("areas"), list):
        return await compute(user)
    areas = []
    for area in stored["areas"]:
        if not isinstance(area, dict) or not area.get("agent_name"):
            continue
        level = levels.get(area["agent_name"], {}).get("level", area.get("level"))
        leveled = area["agent_name"] not in level_rules.UNLEVELED_AGENTS
        if (leveled and level != area.get("level")) or "levels_completed" not in area or area.get("leveled") is not leveled:
            # A level changed, or the snapshot predates level-based scores:
            # the area scores and the overall have to be worked out again.
            return await compute(user)
        areas.append(area)
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
