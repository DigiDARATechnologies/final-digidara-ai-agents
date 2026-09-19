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
