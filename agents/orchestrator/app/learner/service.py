"""Learner profile and per-agent levels, and the context every agent receives."""
from __future__ import annotations

from datetime import datetime

from app import db
from app.learner import levels as level_rules
from app.models import AgentLevel, LearnerProfile

MAX_SKILLS = 30
MAX_SKILL_LENGTH = 60
EXPERIENCE_CHOICES = ("fresher", "experienced")


def _clean_skills(skills: list[str] | None) -> list[str]:
    seen: dict[str, str] = {}
    for raw in skills or []:
        skill = " ".join(str(raw).split())[:MAX_SKILL_LENGTH]
        if skill and skill.lower() not in seen:
            seen[skill.lower()] = skill
        if len(seen) >= MAX_SKILLS:
            break
    return list(seen.values())


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
        profile.target_role = " ".join(target_role.split())[:200]
        profile.degree = " ".join(degree.split())[:200]
        profile.skills = _clean_skills(skills)
        profile.experience = experience
        if profile.onboarding_completed_at is None:
            profile.onboarding_completed_at = datetime.utcnow()
        session.commit()
        session.refresh(profile)
        return _profile_dict(profile)
    finally:
        session.close()


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
    return result


def set_level(user_id: str, agent_name: str, level: str, source: str) -> dict:
    if agent_name not in level_rules.LEVELED_AGENTS:
        raise ValueError(f"Unknown agent {agent_name!r}.")
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
    level = level_rules.normalize(row.level if row else None)
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
    return {"learner_profile": get_profile(user_id), "agent_levels": list(get_levels(user_id).values())}


def purge(user_id: str) -> None:
    session = db.get_session()
    try:
        session.query(AgentLevel).filter_by(user_id=user_id).delete()
        session.query(LearnerProfile).filter_by(user_id=user_id).delete()
        session.commit()
    finally:
        session.close()
