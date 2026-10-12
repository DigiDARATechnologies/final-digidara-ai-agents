"""Learner profile and per-agent levels, and the context every agent receives."""
from __future__ import annotations

from datetime import datetime

from app import db
from app.learner import levels as level_rules
from app.models import AgentLevel, LearnerProfile, ReadinessSnapshot, RoleTrack

MAX_SKILLS = 30
MAX_SKILL_LENGTH = 60
EXPERIENCE_CHOICES = ("fresher", "experienced")


def clean_text(value: str | None, limit: int = 200) -> str:
    """Profile text is kept lowercase with single spaces, so "Data Scientist"
    and "data  scientist" are the same role and the same skill."""
    return " ".join(str(value or "").lower().split())[:limit]


def _clean_skills(skills: list[str] | None) -> list[str]:
    seen: list[str] = []
    for raw in skills or []:
        skill = clean_text(raw, MAX_SKILL_LENGTH)
        if skill and skill not in seen:
            seen.append(skill)
        if len(seen) >= MAX_SKILLS:
            break
    return seen


def _profile_dict(profile: LearnerProfile | None) -> dict:
    if profile is None:
        return {
            "target_role": "", "degree": "", "skills": [], "experience": "fresher",
            "onboarding_completed": False, "onboarding_completed_at": None,
        }
    return {
        "target_role": profile.target_role or "",
        "degree": profile.degree or "",
        "skills": list(profile.skills or []),
        "experience": profile.experience or "fresher",
        "onboarding_completed": profile.onboarding_completed_at is not None,
        "onboarding_completed_at": profile.onboarding_completed_at.isoformat() if profile.onboarding_completed_at else None,
    }


def get_profile(user_id: str) -> dict:
    session = db.get_session()
    try:
        return _profile_dict(session.get(LearnerProfile, user_id))
    finally:
        session.close()


def save_profile(user_id: str, target_role: str, degree: str, skills: list[str], experience: str) -> dict:
    """Create or replace the profile. Saving it is what completes onboarding."""
    experience = experience if experience in EXPERIENCE_CHOICES else "fresher"
    session = db.get_session()
    try:
        profile = session.get(LearnerProfile, user_id)
        if profile is None:
            profile = LearnerProfile(user_id=user_id)
            session.add(profile)
        new_role = clean_text(target_role)
        old_role = clean_text(profile.target_role) if profile.onboarding_completed_at is not None else ""
        if old_role and new_role and old_role != new_role:
            _switch_role(session, user_id, old_role, new_role)
        profile.target_role = new_role
        profile.degree = clean_text(degree)
        profile.skills = _clean_skills(skills)
        profile.experience = experience
        if profile.onboarding_completed_at is None:
            profile.onboarding_completed_at = datetime.utcnow()
        session.commit()
        session.refresh(profile)
        return _profile_dict(profile)
    finally:
        session.close()


def _iso_now() -> str:
    return datetime.utcnow().isoformat()


def _switch_role(session, user_id: str, old_role: str, new_role: str) -> None:
    """Saves the old role's levels and closes its period; the new role starts
    from zero, or from the levels it had when the learner last left it."""
    now = _iso_now()
    old = session.get(RoleTrack, (user_id, old_role))
    if old is None:
        # The role held before tracks existed: everything so far belongs to it.
        old = RoleTrack(user_id=user_id, role_key=old_role, levels={}, periods=[[None, None]])
        session.add(old)
        # Snapshots from before tracks existed were all for the old role.
        session.query(ReadinessSnapshot).filter_by(user_id=user_id, role_key="").update({"role_key": old_role})
    rows = session.query(AgentLevel).filter_by(user_id=user_id).all()
    old.levels = {row.agent_name: {"level": row.level, "source": row.source} for row in rows}
    profile = session.get(LearnerProfile, user_id)
    old.skills = list(profile.skills or []) if profile else []
    old.periods = [list(period) for period in (old.periods or [])]
    if old.periods and old.periods[-1][1] is None:
        old.periods[-1][1] = now
    for row in rows:
        session.delete(row)
    new = session.get(RoleTrack, (user_id, new_role))
    if new is None:
        new = RoleTrack(user_id=user_id, role_key=new_role, levels={}, periods=[])
        session.add(new)
    new.periods = [list(period) for period in (new.periods or [])] + [[now, None]]
    restored = datetime.utcnow()
    for agent_name, saved in (new.levels or {}).items():
        if agent_name in level_rules.LEVELED_AGENTS and isinstance(saved, dict):
            session.add(AgentLevel(user_id=user_id, agent_name=agent_name, level=level_rules.normalize(saved.get("level")),
                                   source=str(saved.get("source") or "self")[:16], updated_at=restored))
    session.flush()


def role_key(user_id: str) -> str:
    """The current target role, as RoleTrack and snapshots key it."""
    session = db.get_session()
    try:
        profile = session.get(LearnerProfile, user_id)
        return clean_text(profile.target_role) if profile else ""
    finally:
        session.close()


def role_periods(user_id: str) -> list[dict] | None:
    """When the current target role was the learner's goal, for agents to
    count only that activity; None when all activity counts (never switched)."""
    session = db.get_session()
    try:
        profile = session.get(LearnerProfile, user_id)
        track = session.get(RoleTrack, (user_id, clean_text(profile.target_role))) if profile else None
    finally:
        session.close()
    periods = [period for period in (track.periods if track else []) or [] if isinstance(period, list) and len(period) == 2]
    if not periods or periods == [[None, None]]:
        return None
    return [{"start": start, "end": end} for start, end in periods]


def role_history(user_id: str) -> list[dict]:
    """Every role the learner has worked towards, with the levels it keeps."""
    session = db.get_session()
    try:
        tracks = session.query(RoleTrack).filter_by(user_id=user_id).all()
    finally:
        session.close()
    return [
        {"role": track.role_key, "skills": list(track.skills or []),
         "levels": {name: (saved or {}).get("level") for name, saved in (track.levels or {}).items()}}
        for track in sorted(tracks, key=lambda t: t.updated_at or datetime.min, reverse=True)
    ]


def get_levels(user_id: str) -> dict[str, dict]:
    """Every leveled agent, with this learner's level (beginner if never set)."""
    session = db.get_session()
    try:
        rows = {row.agent_name: row for row in session.query(AgentLevel).filter_by(user_id=user_id).all()}
    finally:
        session.close()
    result: dict[str, dict] = {}
    for agent_name, label in level_rules.LEVELED_AGENTS.items():
        row = rows.get(agent_name)
        result[agent_name] = {
            "agent_name": agent_name,
            "agent_label": label,
            "level": level_rules.normalize(row.level if row else None),
            "source": row.source if row else "default",
            "updated_at": row.updated_at.isoformat() if row and row.updated_at else None,
        }
    derived = level_rules.DERIVED_AGENT
    if derived in result:
        result[derived].update({
            "level": level_rules.derived_level({name: data["level"] for name, data in result.items()}),
            "source": "derived", "updated_at": None,
        })
    return result


def set_level(user_id: str, agent_name: str, level: str, source: str) -> dict:
    if agent_name not in level_rules.LEVELED_AGENTS:
        raise ValueError(f"Unknown agent {agent_name!r}.")
    if agent_name == level_rules.DERIVED_AGENT:
        raise ValueError("Job Fetching follows your other agents' levels; it cannot be set on its own.")
    if level not in level_rules.LEVELS:
        raise ValueError(f"Level must be one of: {', '.join(level_rules.LEVELS)}.")
    session = db.get_session()
    try:
        row = session.get(AgentLevel, (user_id, agent_name))
        if row is None:
            row = AgentLevel(user_id=user_id, agent_name=agent_name)
            session.add(row)
        row.level = level
        row.source = source
        row.updated_at = datetime.utcnow()
        session.commit()
    finally:
        session.close()
    return get_levels(user_id)[agent_name]


def learner_context(user_id: str, agent_name: str) -> dict:
    """What the gateway adds to every agent call as the envelope's `learner`
    field: the learner's goal, plus their level with this particular agent."""
    session = db.get_session()
    try:
        profile = session.get(LearnerProfile, user_id)
        row = session.get(AgentLevel, (user_id, agent_name))
    finally:
        session.close()
    level = (get_levels(user_id)[agent_name]["level"] if agent_name == level_rules.DERIVED_AGENT
             else level_rules.normalize(row.level if row else None))
    data = _profile_dict(profile)
    from app.memory import service as memory_service  # local import: memory imports nothing from here

    return {
        "target_role": data["target_role"],
        "degree": data["degree"],
        "skills": data["skills"],
        "experience": data["experience"],
        "level": level,
        "difficulty": level_rules.agent_difficulty(agent_name, level),
        # The few memories most relevant to this agent (shared + its own).
        "memory": memory_service.for_agent(user_id, agent_name),
    }


def export_data(user_id: str) -> dict:
    return {"learner_profile": get_profile(user_id), "agent_levels": list(get_levels(user_id).values()),
            "role_tracks": role_history(user_id)}


def purge(user_id: str) -> None:
    session = db.get_session()
    try:
        session.query(AgentLevel).filter_by(user_id=user_id).delete()
        session.query(RoleTrack).filter_by(user_id=user_id).delete()
        session.query(LearnerProfile).filter_by(user_id=user_id).delete()
        session.commit()
    finally:
        session.close()
