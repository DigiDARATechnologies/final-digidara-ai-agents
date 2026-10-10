"""Resume facts: what DigiDARA already knows about a learner, for their resume.

The Resume Builder starts from this instead of asking everything again:
  - the account: name, email and mobile number;
  - the profile: target role, degree, skills and career level;
  - each agent's `resume` block in its student summary (see
    readiness.summarize_reply): Capstone's submitted projects, AI
    Certification's certificates, Coding Practice's languages and solved
    problems;
  - checkable scores: an aptitude or interview average of 70 or more becomes
    an achievement line naming where it was earned.

Only facts the learner earned on DigiDARA or typed into their profile are
used -- nothing is invented -- and `missing` lists what the Resume Builder
still has to ask (phone, location, education details, links, work history).
"""
from __future__ import annotations

from typing import Any

from app.learner import levels as level_rules
from app.learner import service as learner_service
from app.readiness import service as readiness_service

SCORE_ACHIEVEMENT_MIN = 70

SCORE_ACHIEVEMENTS = {
    "aptitude_agent": ("Aptitude: {score:.0f}% average", "DigiDARA aptitude assessments ({count} tests)", "tests_completed"),
    "mock_interview_agent": ("Mock interviews: {score:.0f}/100 average", "DigiDARA AI mock interviews ({count} completed)",
                             "interviews_completed"),
}


def _add_unique(target: list[str], values: list[str]) -> None:
    seen = {v.lower() for v in target}
    for value in values:
        value = " ".join(str(value).split())[:60]
        if value and value.lower() not in seen:
            target.append(value)
            seen.add(value.lower())


def _completed_levels(area: dict) -> dict | None:
    """"Coding Practice: completed Beginner and Medium levels", from the
    levels measured at 100%. Professional repeats Hard, so it is not listed."""
    scores = area.get("level_scores") or {}
    done = [level for level in level_rules.LEVELS[:-1] if (scores.get(level) or 0) >= level_rules.PROMOTE_PROGRESS]
    if not done:
        return None
    names = " and ".join(level_rules.LEVEL_LABELS[level] for level in done)
    plural = "levels" if len(done) > 1 else "level"
    return {"title": f"{area.get('label')}: completed {names} {plural}",
            "description": "DigiDARA leveled practice, measured on every problem or session at that level."}


async def gather(user) -> dict[str, Any]:
    profile = learner_service.get_profile(user.id)
    readiness = await readiness_service.get(user, refresh=True)
    skills: list[str] = []
    _add_unique(skills, profile.get("skills") or [])
    projects: list[dict] = []
    certifications: list[dict] = []
    achievements: list[dict] = []
    sources: list[str] = []
    for area in readiness.get("areas") or []:
        block = area.get("resume") or {}
        used = False
        if block.get("skills"):
            _add_unique(skills, block["skills"])
            used = True
        for key, target in (("projects", projects), ("certifications", certifications), ("achievements", achievements)):
            if block.get(key):
                target.extend(block[key])
                used = True
        rule = SCORE_ACHIEVEMENTS.get(area.get("agent_name"))
        score = area.get("score")
        if rule and area.get("status") == "assessed" and isinstance(score, (int, float)) and score >= SCORE_ACHIEVEMENT_MIN:
            title, description, count_key = rule
            count = (area.get("metrics") or {}).get(count_key) or area.get("activity_count") or 0
            achievements.append({"title": title.format(score=score), "description": description.format(count=count)})
            used = True
        completed = _completed_levels(area)
        if completed:
            achievements.append(completed)
            used = True
        if used:
            sources.append(area.get("label") or area.get("agent_name"))

    phone = (getattr(user, "mobile", None) or "").strip()
    missing = ["location", "education", "linkedin", "github"]
    if not phone:
        missing.insert(0, "phone")
    if not projects:
        missing.append("project")
    if profile.get("experience") == "experienced":
        missing.append("experience")
    return {
        "name": user.name or "",
        "email": user.email,
        "phone": phone,
        "target_role": profile.get("target_role") or "",
        "degree": profile.get("degree") or "",
        "experience_level": profile.get("experience") or "fresher",
        "skills": skills[:20],
        "projects": projects,
        "certifications": certifications,
        "achievements": achievements[:6],
        "sources": sources,
        "missing": missing,
    }
