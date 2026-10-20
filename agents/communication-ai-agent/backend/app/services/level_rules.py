"""How the learner's level shapes Communication practice: the questions asked
and how strictly answers are scored.

Difficulty is stored as easy/medium/hard. The platform has a fourth level,
Professional, which arrives as "hard"; the gateway's signed learner level
(see learner_context) tells it apart, so Professional practice is pitched and
scored above Hard without a new stored difficulty.
"""
from __future__ import annotations

from .learner_context import current


def level_key(difficulty: str) -> str:
    """easy / medium / hard, or professional for a Professional learner."""
    if difficulty == "hard" and str((current() or {}).get("level") or "") == "professional":
        return "professional"
    return difficulty if difficulty in ("easy", "medium", "hard") else "medium"


_GENERATION = {
    # Easy/Medium/Hard question styles already live in each prompt; only
    # Professional adds its own.
    "professional": (
        "PROFESSIONAL LEVEL (above Hard): set a workplace communication task a professional faces -- "
        "explaining a technical decision to a non-technical stakeholder, giving a project status update "
        "with a risk, handling a client complaint, disagreeing politely in a meeting, or writing a concise "
        "email that asks for a decision. Ask for one such task, framed in one or two sentences."
    ),
}

_SCORING = {
    "easy": (
        "LEVEL SCORING -- EASY (beginner): the goal is to be understood. Score generously for simple, "
        "correct sentences on the topic. Only point out errors that change or block the meaning; do not "
        "mark down short answers or simple vocabulary."
    ),
    "medium": (
        "LEVEL SCORING -- MEDIUM: expect a few connected sentences with mostly correct grammar, a reason "
        "or example, and everyday vocabulary used correctly. Point out repeated grammar errors. A one-line "
        "answer with no reason or example is at most 60% of the scale overall."
    ),
    "hard": (
        "LEVEL SCORING -- HARD: expect a well-organised, detailed answer with accurate grammar, linking "
        "words and varied, precise vocabulary. Mark down every grammar error and vague wording. A short, "
        "simple or loosely organised answer is at most 60% of the scale overall."
    ),
    "professional": (
        "LEVEL SCORING -- PROFESSIONAL (workplace standard, stricter than Hard): judge as a manager would "
        "judge a colleague's message: clear structure with the main point first, concise and precise "
        "wording, a professional tone suited to the listener, and error-free grammar. Any casual register, "
        "rambling or grammar error must be marked down; an answer that would not be acceptable at work is at "
        "most 50% of the scale overall."
    ),
}


def generation_rule(difficulty: str) -> str:
    """An extra rule for a question prompt ("" below Professional)."""
    return _GENERATION.get(level_key(difficulty), "")


def scoring_rule(difficulty: str) -> str:
    """How strictly to score an answer at the learner's level."""
    return _SCORING[level_key(difficulty)]
