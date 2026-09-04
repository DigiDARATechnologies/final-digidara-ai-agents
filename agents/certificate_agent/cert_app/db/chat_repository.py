import json
import uuid
import logging
from typing import Dict, List, Optional

from cert_app.db.database import get_connection

logger = logging.getLogger(__name__)

VALID_STATUSES = {'onboarding', 'calibrating', 'ready', 'in_exam', 'grading', 'completed', 'failed', 'generating', 'generation_failed'}
VALID_ROLES = {'user', 'assistant', 'system'}
VALID_MESSAGE_TYPES = {
    'text', 'mcq_question', 'mcq_answer',
    'freetext_question', 'freetext_answer', 'feedback', 'certificate_card', 'take_exam_card'
}


def create_session(user_id: int, topic: str, total_questions: int = 0) -> str:
    """Create a new conversational exam session and return its UUID session_id."""
    session_id = str(uuid.uuid4())
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """INSERT INTO conversation_sessions (id, user_id, topic, status, total_questions)
               VALUES (%s, %s, %s, 'onboarding', %s)""",
            (session_id, user_id, topic, total_questions)
        )
        conn.commit()
        logger.info(f"Created conversation session {session_id} for user {user_id} on topic '{topic}'")
        return session_id
    finally:
        cursor.close()
        conn.close()


def get_user_sessions(user_id: int) -> List[Dict]:
    """Retrieve all conversation sessions for a given user_id ordered by started_at DESC."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            """SELECT id, user_id, topic, status, current_question_index, total_questions, score, exam_id, certificate_id, started_at, completed_at
               FROM conversation_sessions
               WHERE user_id = %s
               ORDER BY started_at DESC""",
            (user_id,)
        )
        rows = cursor.fetchall()
        for row in rows:
            if row.get("started_at"):
                row["started_at"] = str(row["started_at"])
            if row.get("completed_at"):
                row["completed_at"] = str(row["completed_at"])
        return rows
    finally:
        cursor.close()
        conn.close()


def get_session(session_id: str) -> Optional[Dict]:
    """Retrieve a conversation session record by session_id."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT id, user_id, topic, status, current_question_index, total_questions, score, exam_id, certificate_id, started_at, completed_at FROM conversation_sessions WHERE id = %s",
            (session_id,)
        )
        row = cursor.fetchone()
        if not row:
            return None
        # Convert datetimes to ISO strings for JSON serialization
        if row.get("started_at"):
            row["started_at"] = str(row["started_at"])
        if row.get("completed_at"):
            row["completed_at"] = str(row["completed_at"])
        return row
    finally:
        cursor.close()
        conn.close()


def update_session_status(
    session_id: str,
    status: str,
    current_question_index: Optional[int] = None,
    score: Optional[float] = None,
    topic: Optional[str] = None
) -> bool:
    """Update session status, topic, question index, score, or completion timestamp."""
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid status '{status}'. Must be one of {VALID_STATUSES}")

    updates = ["status = %s"]
    params = [status]

    if topic is not None:
        updates.append("topic = %s")
        params.append(topic)

    if current_question_index is not None:
        updates.append("current_question_index = %s")
        params.append(current_question_index)

    if score is not None:
        updates.append("score = %s")
        params.append(score)

    if status in ("completed", "failed"):
        updates.append("completed_at = CURRENT_TIMESTAMP")

    params.append(session_id)
    query = f"UPDATE conversation_sessions SET {', '.join(updates)} WHERE id = %s"

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(query, tuple(params))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        cursor.close()
        conn.close()


def attach_certificate(session_id: str, certificate_id: int) -> bool:
    """Link a chat attempt to its issued certificate for idempotent recovery."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE conversation_sessions SET certificate_id = %s WHERE id = %s",
            (certificate_id, session_id),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        cursor.close()
        conn.close()


def append_message(
    session_id: str,
    role: str,
    content: str,
    message_type: str = "text",
    metadata: Optional[Dict] = None
) -> Dict:
    """Append a chat message to a conversation session."""
    if role not in VALID_ROLES:
        raise ValueError(f"Invalid role '{role}'. Must be one of {VALID_ROLES}")
    if message_type not in VALID_MESSAGE_TYPES:
        raise ValueError(f"Invalid message_type '{message_type}'. Must be one of {VALID_MESSAGE_TYPES}")

    message_id = str(uuid.uuid4())
    metadata_json = json.dumps(metadata) if metadata is not None else None

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            """INSERT INTO chat_messages (id, session_id, role, content, message_type, metadata)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (message_id, session_id, role, content, message_type, metadata_json)
        )
        conn.commit()
        
        cursor.execute(
            "SELECT id, session_id, role, content, message_type, metadata, created_at FROM chat_messages WHERE id = %s",
            (message_id,)
        )
        msg = cursor.fetchone()
        if msg and msg.get("metadata"):
            try:
                msg["metadata"] = json.loads(msg["metadata"])
            except Exception:
                pass
        if msg and msg.get("created_at"):
            msg["created_at"] = str(msg["created_at"])
        return msg
    finally:
        cursor.close()
        conn.close()


def get_message_history(session_id: str) -> List[Dict]:
    """Retrieve full chronological chat message history for a given session_id."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            """SELECT id, session_id, role, content, message_type, metadata, created_at
               FROM chat_messages
               WHERE session_id = %s
               ORDER BY created_at ASC, seq ASC""",
            (session_id,)
        )
        rows = cursor.fetchall()
        for row in rows:
            if row.get("metadata") and isinstance(row["metadata"], str):
                try:
                    row["metadata"] = json.loads(row["metadata"])
                except Exception:
                    pass
            if row.get("created_at"):
                row["created_at"] = str(row["created_at"])
        return rows
    finally:
        cursor.close()
        conn.close()


def store_session_questions(session_id: str, questions: list) -> None:
    """Persist the pre-generated exam questions JSON into conversation_sessions."""
    questions_json = json.dumps(questions)
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE conversation_sessions SET questions_json = %s, total_questions = %s WHERE id = %s",
            (questions_json, len(questions), session_id)
        )
        conn.commit()
    finally:
        cursor.close()
        conn.close()


def get_session_questions(session_id: str) -> list:
    """Retrieve pre-generated exam questions from a conversation session."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT questions_json FROM conversation_sessions WHERE id = %s",
            (session_id,)
        )
        row = cursor.fetchone()
        if not row or not row.get("questions_json"):
            return []
        try:
            return json.loads(row["questions_json"])
        except Exception:
            return []
    finally:
        cursor.close()
        conn.close()
