"""Completed-session question history used to prevent exact repeats."""

import hashlib
import unicodedata

import db


def normalize_role_or_topic(value):
    return " ".join(unicodedata.normalize("NFKC", str(value or "hr")).split()).casefold()


def question_hash(question_text):
    normalized = " ".join(unicodedata.normalize("NFKC", str(question_text)).split()).casefold()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def get_recent_asked_history(user_id, round_type, role_or_topic, difficulty, window=10):
    """Return hashes and text from the latest completed sessions in this scope.

    ``difficulty`` is retained in the public helper signature, but the history
    scope intentionally spans difficulties: user + round + normalized topic.
    """
    scope = normalize_role_or_topic(role_or_topic)
    rows, _ = db.query(
        """SELECT h.question_hash, h.question_text
           FROM user_question_history h
           WHERE h.user_id = %s AND h.round_type = %s AND h.role_or_topic = %s
             AND h.interview_session_id IN (
                SELECT session_id FROM (
                    SELECT h2.interview_session_id AS session_id
                    FROM user_question_history h2
                    JOIN interviews i ON i.id = h2.interview_session_id
                    WHERE h2.user_id = %s AND h2.round_type = %s
                      AND h2.role_or_topic = %s AND i.status = 'completed'
                    GROUP BY h2.interview_session_id
                    ORDER BY MAX(h2.served_at) DESC
                    LIMIT %s
                ) AS recent_sessions
             )""",
        (user_id, round_type, scope, user_id, round_type, scope, window),
        fetch=True,
    )
    return {row["question_hash"] for row in rows}, [row["question_text"] for row in rows]


def get_recent_asked_hashes(user_id, round_type, role_or_topic, difficulty, window=10):
    return get_recent_asked_history(user_id, round_type, role_or_topic, difficulty, window)[0]


def get_recent_skill_coverage(user_id, role_name, round_type, difficulty):
    """Return skill areas ordered by when they were last covered.

    The scope is deliberately the same student, role, round, and difficulty
    as the current interview.  A missing skill is returned first by callers,
    so short interviews eventually cover the complete role skill set.
    """
    if not role_name or round_type != "technical":
        return []
    rows, _ = db.query(
        """SELECT d.subject_tag, MAX(d.created_at) AS last_covered
           FROM interview_details d
           JOIN interviews i ON i.id = d.interview_id
           WHERE i.student_id = %s AND i.round_type = %s
             AND LOWER(TRIM(i.role_name)) = LOWER(TRIM(%s))
             AND i.difficulty = %s
             AND d.is_followup = FALSE AND d.subject_tag IS NOT NULL
             AND i.status IN ('completed', 'exited')
           GROUP BY d.subject_tag
           ORDER BY last_covered ASC""",
        (user_id, round_type, role_name, difficulty),
        fetch=True,
    )
    if not isinstance(rows, list):
        return []
    return [str(row["subject_tag"]).strip() for row in rows if row.get("subject_tag")]


def prioritize_skill_areas(skill_areas, recently_covered):
    """Put never/least-recently-covered skills first, preserving stable ties."""
    skills = [str(skill).strip() for skill in (skill_areas or []) if str(skill).strip()]
    recency = {
        " ".join(str(skill).split()).casefold(): index
        for index, skill in enumerate(recently_covered or [])
    }
    return sorted(
        skills,
        key=lambda skill: (
            0 if " ".join(skill.split()).casefold() not in recency else 1,
            recency.get(" ".join(skill.split()).casefold(), -1),
            skills.index(skill),
        ),
    )


def record_served_questions(user_id, round_type, role_or_topic, difficulty, interview_session_id, questions):
    scope = normalize_role_or_topic(role_or_topic)
    for item in questions:
        text = item["question"]
        db.query(
            """INSERT INTO user_question_history
                 (user_id, round_type, role_or_topic, difficulty, question_text,
                  question_hash, source, interview_session_id)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (user_id, round_type, scope, difficulty, text, question_hash(text),
             item.get("source", "ai_generated"), interview_session_id),
        )
