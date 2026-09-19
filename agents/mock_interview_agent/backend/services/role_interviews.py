"""Additive role-interview resolution and deterministic subject rotation."""

import json
import logging

from ai.question_generation import PRESET_SUBJECTS
from ai.validators import _question_payload

logger = logging.getLogger(__name__)


ROLE_SUBJECTS = {
    "python fullstack developer": ["python", "mysql", "javascript", "react", "flask"],
    "data analyst": ["data science", "mysql", "power bi", "python"],
    "data scientist": ["python", "data science", "mysql", "machine learning"],
    "digital marketing executive": ["seo", "sem & google ads", "social media marketing", "content marketing", "email marketing"],
    "ai engineer": ["python", "machine learning", "generative ai", "rag & vector databases", "fastapi"],
}

# Older role interviews grouped several data skills under the broad ``python``
# subject tag.  Map that legacy recommendation to a deliberately core-language
# retest rather than letting it drift into Pandas, statistics, or Excel.
WEAK_TOPIC_ALIASES = {
    "python": "Python fundamentals",
    "pandas": "Pandas and DataFrames",
    "numpy": "NumPy basics",
    "statistics": "Statistics fundamentals",
    "data visualization": "Data visualization basics",
    "excel": "Excel basics",
    "sql": "SQL basics",
}


def normalize_role(value):
    return " ".join(str(value or "").split()).strip()


def normalize_weak_topic_areas(areas):
    """Canonicalize legacy broad tags while preserving exact stored topics."""
    normalized, seen = [], set()
    for area in areas or []:
        text = normalize_role(area)
        canonical = WEAK_TOPIC_ALIASES.get(text.casefold(), text)
        key = canonical.casefold()
        if canonical and key not in seen:
            seen.add(key)
            normalized.append(canonical)
    return normalized


def resolve_role_subjects(role, *, chat_fn):
    """Resolve a role to a small practical stack; custom roles use one LLM call."""
    role = normalize_role(role)
    preset = ROLE_SUBJECTS.get(role.casefold())
    if preset:
        logger.info("Resolved preset role %r to subjects: %s", role, preset,
                    extra={"event": "role_subjects_resolved"})
        return preset
    raw = chat_fn([
        {"role": "system", "content": (
            "Resolve a job role into 3 to 6 practical interview subjects. "
            "Use common technologies or skills a real interviewer would assess. "
            "Reply only with JSON: {\"subjects\":[\"subject\"]}."
        )},
        {"role": "user", "content": f"Role: {role}"},
    ], json_mode=True)
    value = json.loads(raw)
    subjects = value.get("subjects") if isinstance(value, dict) else None
    if not isinstance(subjects, list):
        raise ValueError("The AI returned an invalid role subject list.")
    cleaned = []
    seen = set()
    for subject in subjects:
        text = normalize_role(subject).casefold()
        if text and len(text) <= 150 and text not in seen:
            seen.add(text)
            cleaned.append(text)
    if not 3 <= len(cleaned) <= 6:
        raise ValueError("The AI must return 3 to 6 role subjects.")
    logger.info("Resolved custom role %r to subjects: %s", role, cleaned,
                extra={"event": "role_subjects_resolved"})
    return cleaned


def subject_for_question(subjects, main_question_index):
    """Round-robin coverage gives every role subject a predictable turn."""
    return subjects[main_question_index % len(subjects)]


def role_subject_prompt(role, subject):
    return (
        f"This is a {role} interview. Ask the kind of question a real interviewer "
        f"would prioritize for a {role} candidate on {subject}: core concepts most "
        "frequently tested in real interviews, not obscure or filler topics."
    )


def subject_breakdown(rows):
    """Return Strong/Weak labels from each question's specific topic area.

    ``subject_tag`` is a broad role-stack label (for example ``python``).
    It must not collapse a Pandas or statistics question into a generic Python
    retest.  Old rows without ``topic_area`` retain their subject-tag fallback.
    """
    grouped = {}
    for row in rows:
        topic_area = row.get("topic_area") or row.get("subject_tag")
        if not topic_area:
            continue
        verdict = row.get("verdict")
        score = {"correct": 1, "partial": 0.5, "wrong": 0}.get(verdict, 0)
        grouped.setdefault(topic_area, []).append(score)
    strong, weak, details = [], [], []
    for subject, scores in grouped.items():
        average = sum(scores) / len(scores)
        status = "Strong" if average >= 0.6 else "Weak"
        (strong if status == "Strong" else weak).append(subject)
        details.append({"subject": subject, "status": status, "score": round(average, 2)})
    logger.info(
        "Computed role weak areas from question topic_area values: %s",
        details,
        extra={"event": "role_topic_area_breakdown"},
    )
    return {"strong_subjects": strong, "weak_subjects": weak, "subjects": details}
