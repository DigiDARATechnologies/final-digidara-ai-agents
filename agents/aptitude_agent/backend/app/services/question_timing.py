"""Difficulty-based question timing shared by all assessment modes."""

from flask import current_app


DIFFICULTY_TIME_CONFIG={
    "easy":("QUESTION_SECONDS_EASY",60),
    "beginner":("QUESTION_SECONDS_EASY",60),
    "medium":("QUESTION_SECONDS_MEDIUM",90),
    "intermediate":("QUESTION_SECONDS_MEDIUM",90),
    "hard":("QUESTION_SECONDS_HARD",120),
    "advanced":("QUESTION_SECONDS_HARD",120),
}


def question_time_seconds(difficulty,config=None):
    """Return the authoritative timer for either difficulty naming scheme."""
    normalized=str(difficulty or "").strip().casefold()
    setting=DIFFICULTY_TIME_CONFIG.get(normalized)
    if not setting:
        raise ValueError(f"Unsupported question difficulty: {difficulty}")
    key,default=setting
    settings=current_app.config if config is None else config
    seconds=int(settings.get(key,default))
    if seconds<1:
        raise ValueError(f"{key} must be a positive number of seconds")
    return seconds
