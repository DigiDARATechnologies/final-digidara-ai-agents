"""The platform's four learner levels and how each agent spells them.

Every learner starts at "beginner" with every agent. The level travels to the
agent in the gateway's `learner` envelope field, and for the actions listed
in DIFFICULTY_ACTIONS it also becomes the action's `difficulty` when the
browser did not choose one, translated to the words that agent accepts.
"""
from __future__ import annotations

LEVELS: tuple[str, ...] = ("beginner", "medium", "hard", "professional")
DEFAULT_LEVEL = "beginner"

LEVEL_LABELS = {
    "beginner": "Beginner",
    "medium": "Medium",
    "hard": "Hard",
    "professional": "Professional",
}

# Registry agent name -> name shown to learners. The same eight agents the
# gateway serves; job_agent's level frames which jobs are suggested (entry
# level for a beginner) rather than a question difficulty.
LEVELED_AGENTS: dict[str, str] = {
    "aptitude_agent": "Aptitude Trainer",
    "codeforge_agent": "Coding Practice",
    "communication_agent": "Communication Coach",
    "mock_interview_agent": "Mock Interview",
    "resume_builder_agent": "Resume Builder",
    "capstone_project_agent": "Capstone Project",
    "certificate_agent": "AI Certification",
    "job_agent": "Job Fetching",
}

_EASY_MEDIUM_HARD = {"beginner": "easy", "medium": "medium", "hard": "hard", "professional": "hard"}
_BEGINNER_TO_ADVANCED = {
    "beginner": "beginner", "medium": "intermediate", "hard": "advanced", "professional": "advanced",
}

# How each agent words difficulty, for agents that take one.
AGENT_DIFFICULTY: dict[str, dict[str, str]] = {
    "aptitude_agent": _EASY_MEDIUM_HARD,
    "codeforge_agent": _EASY_MEDIUM_HARD,
    "communication_agent": _EASY_MEDIUM_HARD,
    "capstone_project_agent": _EASY_MEDIUM_HARD,
    "mock_interview_agent": _BEGINNER_TO_ADVANCED,
    "certificate_agent": _BEGINNER_TO_ADVANCED,
}

# Actions whose request body takes `difficulty`, verified against each
# agent's own route (e.g. mock_interview_agent routes/interviews.py requires
# beginner|intermediate|advanced). Only these get a default filled in; any
# value the browser sent is always kept.
DIFFICULTY_ACTIONS: dict[str, frozenset[str]] = {
    "mock_interview_agent": frozenset({"start_interview"}),
    "communication_agent": frozenset({
        "writing_start", "speaking_start", "practice_generate_topic",
        "pronunciation_generate", "pronunciation_session_start",
    }),
}


# Level progress (0-100) is how much of the learner's current level they have
# done with an agent: Coding counts solved problems at that difficulty; an
# agent that cannot measure it yet uses its readiness score. At UNLOCK_PROGRESS
# the learner may move up; at PROMOTE_PROGRESS readiness moves them up itself.
UNLOCK_PROGRESS = 50
PROMOTE_PROGRESS = 100


def next_level(level: str) -> str | None:
    index = LEVELS.index(normalize(level))
    return LEVELS[index + 1] if index + 1 < len(LEVELS) else None


def is_higher(level: str, than: str) -> bool:
    return LEVELS.index(normalize(level)) > LEVELS.index(normalize(than))


def normalize(level: str | None) -> str:
    value = (level or "").strip().lower()
    return value if value in LEVELS else DEFAULT_LEVEL


def agent_difficulty(agent_name: str, level: str) -> str | None:
    vocabulary = AGENT_DIFFICULTY.get(agent_name)
    return vocabulary.get(normalize(level)) if vocabulary else None


def suggested_level(score: float | None) -> str | None:
    """The level a readiness score points to; None without a score."""
    if score is None:
        return None
    if score >= 85:
        return "professional"
    if score >= 65:
        return "hard"
    if score >= 40:
        return "medium"
    return "beginner"
