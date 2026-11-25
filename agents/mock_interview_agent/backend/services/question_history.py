"""Completed-session question history used to prevent exact repeats."""

import hashlib
import re
import unicodedata
from difflib import SequenceMatcher

import db


def normalize_role_or_topic(value):
    return " ".join(unicodedata.normalize("NFKC", str(value or "hr")).split()).casefold()


def question_hash(question_text):
    normalized = " ".join(unicodedata.normalize("NFKC", str(question_text)).split()).casefold()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


_WORD = re.compile(r"[a-z0-9+#]+")
# Words that carry no meaning of their own, so "What is a Python list?" and
# "What's a list in Python?" compare as the same question.
_FILLER_WORDS = frozenset((
    "a an the is are was were be been do does did can could would should will "
    "you your we our i me my it its this that these those of in on at to for "
    "with by from about into as and or what whats how why when where which who "
    "explain describe tell define give please briefly s"
).split())


def _content_words(question_text):
    normalized = unicodedata.normalize("NFKC", str(question_text or "")).casefold()
    return [word for word in _WORD.findall(normalized) if word not in _FILLER_WORDS]


def questions_are_similar(first, second):
    """True when two questions are the same question, even if reworded."""
    if question_hash(first) == question_hash(second):
        return True
    first_words, second_words = _content_words(first), _content_words(second)
    if not first_words or not second_words:
        return False
    first_set, second_set = set(first_words), set(second_words)
    if first_set == second_set:
        return True
    if min(len(first_set), len(second_set)) >= 3:
        # One question is the other with a single extra word.
        smaller, larger = sorted((first_set, second_set), key=len)
        if smaller <= larger and len(larger - smaller) <= 1:
            return True
        overlap = len(first_set & second_set) / len(first_set | second_set)
        if overlap >= 0.8:
            return True
    return SequenceMatcher(None, " ".join(first_words), " ".join(second_words)).ratio() >= 0.9


def is_repeated_question(question_text, asked_questions):
    """True when ``question_text`` repeats any question in ``asked_questions``."""
    return any(
        questions_are_similar(question_text, asked)
        for asked in asked_questions
        if isinstance(asked, str) and asked.strip()
    )


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
