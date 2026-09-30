"""Per-learner record of every exam question already given, so no learner is
asked the same question twice across attempts."""
import hashlib
import logging
from typing import Iterable, List

from cert_app.db.database import get_connection

logger = logging.getLogger(__name__)


def _topic_key(topic: str) -> str:
    return " ".join((topic or "").lower().split())[:255]


def _question_hash(text: str) -> str:
    # Imported lazily: question_agent imports from the db package.
    from cert_app.agents.question_agent import normalize_question_text
    return hashlib.sha256(normalize_question_text(text).encode("utf-8")).hexdigest()


def get_seen_questions(user_id: int, topic: str, limit: int = 500) -> List[str]:
    """Questions this learner was already given for `topic`, newest first.

    Never raises: history only improves variety, so a lookup failure must not
    block an exam from being generated.
    """
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                """SELECT question_text FROM user_question_history
                   WHERE user_id = %s AND topic = %s
                   ORDER BY id DESC LIMIT %s""",
                (user_id, _topic_key(topic), limit),
            )
            return [row["question_text"] for row in cursor.fetchall()]
        finally:
            cursor.close()
            conn.close()
    except Exception as e:
        logger.warning(f"[QuestionHistory] Could not load history for user {user_id}: {e}")
        return []


def record_seen_questions(user_id: int, topic: str, questions: Iterable) -> None:
    """Remember the questions given to a learner. Accepts question dicts or strings."""
    rows = []
    for q in questions or []:
        text = (q.get("question") or q.get("question_text")) if isinstance(q, dict) else q
        text = str(text or "").strip()
        if text:
            rows.append((user_id, _topic_key(topic), _question_hash(text), text))
    if not rows:
        return
    try:
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.executemany(
                """INSERT IGNORE INTO user_question_history (user_id, topic, question_hash, question_text)
                   VALUES (%s, %s, %s, %s)""",
                rows,
            )
            conn.commit()
        finally:
            cursor.close()
            conn.close()
    except Exception as e:
        logger.warning(f"[QuestionHistory] Could not record history for user {user_id}: {e}")
