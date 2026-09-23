"""
db.py
Small helper around mysql-connector so app.py stays clean.
"""

import os
import json
from dotenv import load_dotenv
import mysql.connector
from mysql.connector import pooling

load_dotenv()

dbconfig = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "user": os.environ.get("DB_USER", "root"),
    "password": os.environ.get("DB_PASSWORD", ""),
    "database": os.environ.get("DB_NAME", "mock_interview_db"),
}

MAX_POOL_SIZE = 4


def pool_size_from_env(value):
    """mysql-connector opens every pooled connection eagerly, per gunicorn
    worker, on a MySQL server shared with the other agents. The old default of
    10 x 4 workers hit "1040 Too many connections" on deploy, so cap it even
    if an older .env still says DB_POOL_SIZE=10."""
    try:
        requested = int(value) if value else MAX_POOL_SIZE
    except ValueError:
        requested = MAX_POOL_SIZE
    return max(1, min(requested, MAX_POOL_SIZE))


pool = pooling.MySQLConnectionPool(
    pool_name="mi_pool",
    pool_size=pool_size_from_env(os.environ.get("DB_POOL_SIZE")),
    pool_reset_session=True,
    **dbconfig,
)


def get_conn():
    return pool.get_connection()


def query(sql, params=None, fetch=False, fetchone=False):
    conn = get_conn()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(sql, params or ())
        if fetchone:
            result = cursor.fetchone()
        elif fetch:
            result = cursor.fetchall()
        else:
            result = None
        conn.commit()
        last_id = cursor.lastrowid
        return result, last_id
    finally:
        cursor.close()
        conn.close()


def execute_update(sql, params=None):
    """Execute one write and return the number of rows actually changed."""
    conn = get_conn()
    cursor = conn.cursor()
    try:
        cursor.execute(sql, params or ())
        affected_rows = cursor.rowcount
        conn.commit()
        return affected_rows
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


def create_or_resume_interview(
    student_id,
    round_type,
    subject,
    difficulty,
    num_questions,
    first_question,
    first_topic_area=None,
    *,
    interview_mode="course",
    role_name=None,
    resolved_subjects=None,
    first_subject_tag=None,
    question_plan=None,
):
    """Atomically create the interview and first question, or resume the active one."""
    conn = get_conn()
    cursor = conn.cursor(dictionary=True)
    try:
        conn.start_transaction()

        # Lock one stable row per student. Concurrent starts for the same
        # student must pass this point one at a time, including across workers.
        cursor.execute(
            "SELECT id FROM students WHERE id = %s FOR UPDATE",
            (student_id,),
        )
        if not cursor.fetchone():
            conn.rollback()
            return {"student_exists": False}

        cursor.execute(
            """SELECT id, round_type, interview_mode, role_name, resolved_subjects, difficulty, num_questions
               FROM interviews
               WHERE student_id = %s AND status = 'in_progress'
               ORDER BY started_at DESC, id DESC
               LIMIT 1""",
            (student_id,),
        )
        active = cursor.fetchone()
        orphaned_interview_id = None
        if active:
            cursor.execute(
                """SELECT question_order, question, question_source, topic_area, is_followup
                   FROM interview_details
                   WHERE interview_id = %s
                   ORDER BY question_order DESC, id DESC
                   LIMIT 1""",
                (active["id"],),
            )
            current = cursor.fetchone()
            if current:
                cursor.execute(
                    """SELECT COUNT(*) AS real_question_index
                       FROM interview_details
                       WHERE interview_id = %s AND is_followup = FALSE
                         AND question_order <= %s""",
                    (active["id"], current["question_order"]),
                )
                counts = cursor.fetchone()
                conn.commit()
                return {
                    "student_exists": True,
                    "created": False,
                    "interview_id": active["id"],
                    "question_order": current["question_order"],
                    "question": current["question"],
                    "question_source": current.get("question_source"),
                    "topic_area": current.get("topic_area"),
                    "is_followup": bool(current["is_followup"]),
                    "difficulty": active["difficulty"],
                    "round_type": active["round_type"],
                    "interview_mode": active.get("interview_mode", "course"),
                    "role_name": active.get("role_name"),
                    "resolved_subjects": active.get("resolved_subjects"),
                    "total_questions": int(active["num_questions"]),
                    "real_question_index": int(
                        counts["real_question_index"] or 1
                    ),
                }

            # Preserve the historical row but remove an unrecoverable orphan
            # from the active-session set before creating its replacement.
            orphaned_interview_id = active["id"]
            cursor.execute(
                """UPDATE interviews
                   SET status = 'exited', ended_at = NOW()
                   WHERE id = %s AND status = 'in_progress'""",
                (orphaned_interview_id,),
            )

        cursor.execute(
            """INSERT INTO interviews
                 (student_id, round_type, interview_mode, subject, role_name,
                  resolved_subjects, difficulty, num_questions, status)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'in_progress')""",
            (student_id, round_type, interview_mode, subject, role_name,
             json.dumps(resolved_subjects) if resolved_subjects else None,
             difficulty, num_questions),
        )
        interview_id = cursor.lastrowid
        plan = question_plan or [{
            "question": first_question,
            "topic_area": first_topic_area,
            "subject_tag": first_subject_tag,
        }]
        for question_order, item in enumerate(plan, start=1):
            cursor.execute(
                """INSERT INTO interview_details
                     (interview_id, question_order, question, question_source, topic_area, subject_tag, is_followup)
                   VALUES (%s, %s, %s, %s, %s, %s, FALSE)""",
                (
                    interview_id, question_order, item["question"],
                    item.get("source", "ai_generated"), item.get("topic_area"),
                    item.get("subject_tag", first_subject_tag),
                ),
            )
            if question_order == 1:
                first_detail_id = cursor.lastrowid
        conn.commit()
        return {
            "student_exists": True,
            "created": True,
            "interview_id": interview_id,
            "first_detail_id": first_detail_id,
            "orphaned_interview_id": orphaned_interview_id,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


def save_answer_with_optional_daily_usage(
    detail_id,
    student_id,
    usage_date,
    answer,
    time_taken_sec,
    daily_limit,
    count_toward_daily_limit,
):
    """
    Save a first-time, non-empty answer transactionally.

    Planned main questions increment the student's daily usage. The
    is_followup flag remains for historical rows; those answers do not
    consume quota. Retries are safe: one main question row can consume at
    most one quota unit.
    """
    conn = get_conn()
    cursor = conn.cursor(dictionary=True)
    try:
        conn.start_transaction()
        answered_count = 0
        if count_toward_daily_limit:
            cursor.execute(
                """INSERT IGNORE INTO daily_usage
                     (student_id, usage_date, answered_count)
                   VALUES (%s, %s, 0)""",
                (student_id, usage_date),
            )
            cursor.execute(
                """SELECT answered_count
                   FROM daily_usage
                   WHERE student_id = %s AND usage_date = %s
                   FOR UPDATE""",
                (student_id, usage_date),
            )
            usage = cursor.fetchone()
            answered_count = int(usage["answered_count"]) if usage else 0

            if answered_count >= daily_limit:
                conn.rollback()
                return {
                    "saved": False,
                    "limit_reached": True,
                    "answered_count": answered_count,
                }

        cursor.execute(
            """UPDATE interview_details
               SET answer = %s, answered_at = NOW(), time_taken_sec = %s,
                   processing_status = 'answer_received',
                   processing_error = NULL
               WHERE id = %s AND answer IS NULL AND verdict IS NULL""",
            (answer, time_taken_sec, detail_id),
        )
        if cursor.rowcount != 1:
            conn.rollback()
            return {
                "saved": False,
                "limit_reached": False,
                "answered_count": answered_count,
            }

        if count_toward_daily_limit:
            cursor.execute(
                """UPDATE daily_usage
                   SET answered_count = answered_count + 1
                   WHERE student_id = %s AND usage_date = %s""",
                (student_id, usage_date),
            )
            answered_count += 1

        conn.commit()
        return {
            "saved": True,
            "limit_reached": False,
            "answered_count": answered_count,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()
