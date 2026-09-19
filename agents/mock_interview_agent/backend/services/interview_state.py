"""Shared interview quota, history, and active-session queries."""

from datetime import datetime
import unicodedata

import db
from settings import (
    DAILY_ANSWER_LIMIT,
    DAILY_LIMIT_ENABLED,
    DAILY_QUOTA_TIMEZONE,
)


def usage_date():
    """Return the institute's current calendar date for daily quota resets."""
    return datetime.now(DAILY_QUOTA_TIMEZONE).date()


def daily_answered_count(student_id, requested_date=None):
    if not DAILY_LIMIT_ENABLED:
        return 0
    day = requested_date or usage_date()
    row, _ = db.query(
        """SELECT answered_count
           FROM daily_usage
           WHERE student_id = %s AND usage_date = %s""",
        (student_id, day),
        fetchone=True,
    )
    return int(row["answered_count"]) if row else 0


def quota_payload(answered_count):
    if not DAILY_LIMIT_ENABLED:
        return {
            "daily_limit_enabled": False,
            "daily_limit": DAILY_ANSWER_LIMIT,
            "daily_answered_count": None,
            "daily_remaining": None,
            "daily_limit_reached": False,
        }
    remaining = max(DAILY_ANSWER_LIMIT - answered_count, 0)
    return {
        "daily_limit_enabled": True,
        "daily_limit": DAILY_ANSWER_LIMIT,
        "daily_answered_count": answered_count,
        "daily_remaining": remaining,
        "daily_limit_reached": remaining == 0,
    }


def recent_questions_for_student(
    student_id, round_type, subject, difficulty, limit=40
):
    """Return recent main questions from matching completed or exited interviews."""
    rows, _ = db.query(
        """SELECT d.question
           FROM interview_details d
           JOIN interviews i ON i.id = d.interview_id
           WHERE i.student_id = %s AND i.round_type = %s
             AND i.subject <=> %s AND i.difficulty = %s
             AND d.is_followup = FALSE
             AND i.status IN ('completed', 'exited')
           ORDER BY d.created_at DESC, d.id DESC
           LIMIT %s""",
        (student_id, round_type, subject, difficulty, limit),
        fetch=True,
    )
    return [row["question"] for row in rows]


def canonical_subject(value):
    """Return the stable comparison key used for free-text technical topics."""
    if value is None:
        return None
    return " ".join(
        unicodedata.normalize("NFKC", str(value)).split()
    ).strip().casefold()


def recent_topic_areas_for_student(
    student_id, round_type, subject, limit=80
):
    """Return recent main-question topic labels across matching difficulties."""
    params = [student_id, round_type]
    if subject is None:
        subject_predicate = "i.subject IS NULL"
    else:
        subject_predicate = (
            "LOWER(REGEXP_REPLACE(TRIM(i.subject), '[[:space:]]+', ' ')) = %s"
        )
        params.append(canonical_subject(subject))
    params.append(limit)
    rows, _ = db.query(
        f"""SELECT d.topic_area
            FROM interview_details d
            JOIN interviews i ON i.id = d.interview_id
            WHERE i.student_id = %s AND i.round_type = %s
              AND {subject_predicate}
              AND d.is_followup = FALSE
              AND d.topic_area IS NOT NULL
              AND i.status IN ('completed', 'exited')
            ORDER BY d.created_at DESC, d.id DESC
            LIMIT %s""",
        tuple(params),
        fetch=True,
    )
    return [row["topic_area"] for row in rows]


def merge_question_context(*question_groups):
    """Merge question groups while removing normalized textual duplicates.

    Groups retain their input order, so callers can put the current interview
    first and guarantee that its wording is preserved ahead of older history.
    """
    merged = []
    seen = set()
    for group in question_groups:
        for question in group:
            if not isinstance(question, str):
                continue
            cleaned = " ".join(
                unicodedata.normalize("NFKC", question).split()
            ).strip()
            if not cleaned:
                continue
            key = cleaned.casefold().rstrip("?.!。？！").rstrip()
            if not key or key in seen:
                continue
            seen.add(key)
            merged.append(cleaned)
    return merged


def merge_topic_area_context(*topic_groups):
    """Normalize and de-duplicate topic labels while preserving recency order."""
    merged = []
    seen = set()
    for group in topic_groups:
        for topic_area in group:
            normalized = canonical_subject(topic_area)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            merged.append(normalized)
    return merged


def active_interview_payload(student_id):
    """Return the student's latest recoverable active session, if one exists."""
    interview, _ = db.query(
        """SELECT id, round_type, interview_mode, role_name, resolved_subjects, difficulty, num_questions
           FROM interviews
           WHERE student_id = %s AND status = 'in_progress'
           ORDER BY started_at DESC, id DESC
           LIMIT 1""",
        (student_id,),
        fetchone=True,
    )
    if not interview:
        return None
    current, _ = db.query(
        """SELECT id, question_order, question, question_source, topic_area, subject_tag, is_followup, answer,
                  verdict, processing_status
           FROM interview_details
           WHERE interview_id = %s
             AND answer IS NULL AND verdict IS NULL AND timed_out = FALSE
           ORDER BY question_order, id
           LIMIT 1""",
        (interview["id"],),
        fetchone=True,
    )
    if not current:
        return {
            "active": False,
            "orphaned_interview_id": interview["id"],
        }
    counts, _ = db.query(
        """SELECT COUNT(*) AS real_question_index
           FROM interview_details
           WHERE interview_id = %s AND is_followup = FALSE
             AND question_order <= %s""",
        (interview["id"], current["question_order"]),
        fetchone=True,
    )
    return {
        "active": True,
        "interview_id": interview["id"],
        "question_order": current["question_order"],
        **format_question_for_display(current),
        "topic_area": current.get("topic_area"),
        "is_followup": bool(current["is_followup"]),
        "difficulty": interview["difficulty"],
        "round_type": interview["round_type"],
        "interview_mode": interview.get("interview_mode", "course"),
        "role_name": interview.get("role_name"),
        "resolved_subjects": interview.get("resolved_subjects"),
        "subject_tag": current.get("subject_tag"),
        "total_questions": int(interview["num_questions"]),
        "real_question_index": int(counts["real_question_index"] or 1),
        "has_saved_answer": current["answer"] is not None,
        "processing_status": current["processing_status"],
    }


def format_question_for_display(question_obj):
    """Return display-only metadata without modifying stored question text."""
    return {
        "question": question_obj["question"],
        "is_frequently_asked": question_obj.get("question_source") == "real"
        or question_obj.get("source") == "real",
    }
