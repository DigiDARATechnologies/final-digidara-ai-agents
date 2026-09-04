import json
import mysql.connector
from mysql.connector import pooling
import logging
from typing import Optional, List, Dict

from cert_app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

_pool = None


def get_pool():
    global _pool
    if _pool is None:
        _pool = mysql.connector.pooling.MySQLConnectionPool(
            pool_name="cert_pool",
            pool_size=10,
            host=settings.DB_HOST,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD,
            database=settings.DB_NAME,
        )
    return _pool


def get_connection():
    return get_pool().get_connection()


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INT PRIMARY KEY AUTO_INCREMENT,
        name VARCHAR(255) NOT NULL,
        email VARCHAR(255) UNIQUE NOT NULL,
        hashed_password VARCHAR(255) NOT NULL,
        is_active BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS attempt_tracking (
        id INT PRIMARY KEY AUTO_INCREMENT,
        user_id INT NOT NULL,
        topic VARCHAR(255) NOT NULL,
        attempts INT DEFAULT 0,
        is_locked BOOLEAN DEFAULT FALSE,
        last_attempt_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        UNIQUE KEY unique_user_topic (user_id, topic),
        FOREIGN KEY (user_id) REFERENCES users(id)
    )""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS exams (
        id INT PRIMARY KEY AUTO_INCREMENT,
        user_id INT NOT NULL,
        topic VARCHAR(255) NOT NULL,
        total_questions INT DEFAULT 0,
        correct_answers INT DEFAULT 0,
        score_percentage FLOAT DEFAULT 0.0,
        status VARCHAR(50) DEFAULT 'started',
        started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        completed_at TIMESTAMP NULL,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS questions (
        id INT PRIMARY KEY AUTO_INCREMENT,
        -- Chat-mode certification attempts do not create a traditional
        -- `exams` row. Keep the relationship optional so a passed chat exam
        -- can still persist and serve its PDF certificate.
        exam_id INT NULL,
        question_text TEXT NOT NULL,
        expected_answer TEXT NOT NULL,
        options JSON,
        correct_answer TEXT,
        difficulty ENUM('beginner','intermediate','advanced') DEFAULT 'beginner',
        order_num INT NOT NULL,
        FOREIGN KEY (exam_id) REFERENCES exams(id)
    )""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_answers (
        id INT PRIMARY KEY AUTO_INCREMENT,
        exam_id INT NOT NULL,
        question_id INT NOT NULL,
        user_answer TEXT,
        score INT DEFAULT 0,
        ai_feedback TEXT,
        FOREIGN KEY (exam_id) REFERENCES exams(id),
        FOREIGN KEY (question_id) REFERENCES questions(id)
    )""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS certificates (
        id INT PRIMARY KEY AUTO_INCREMENT,
        user_id INT NOT NULL,
        exam_id INT NOT NULL,
        topic VARCHAR(255) NOT NULL,
        score_percentage FLOAT NOT NULL,
        certificate_number VARCHAR(50) UNIQUE NOT NULL,
        recipient_name VARCHAR(255) NULL,
        file_path VARCHAR(500),
        issued_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (exam_id) REFERENCES exams(id)
    )""")

    # A certificate is only emailed after its recipient proves access to the
    # destination inbox with a short-lived one-time code.
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS certificate_email_verifications (
        id BIGINT PRIMARY KEY AUTO_INCREMENT,
        user_id INT NOT NULL,
        certificate_id INT NOT NULL,
        email VARCHAR(255) NOT NULL,
        code_hash CHAR(64) NOT NULL,
        attempts INT NOT NULL DEFAULT 0,
        expires_at DATETIME NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_certificate_email_verification (user_id, certificate_id, email),
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (certificate_id) REFERENCES certificates(id) ON DELETE CASCADE
    )""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS certificate_usage_events (
        id BIGINT PRIMARY KEY AUTO_INCREMENT,
        action_name VARCHAR(100) NOT NULL,
        event_type ENUM('request', 'model') NOT NULL DEFAULT 'request',
        input_tokens INT NOT NULL DEFAULT 0,
        output_tokens INT NOT NULL DEFAULT 0,
        total_tokens INT NOT NULL DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_certificate_usage_created (created_at),
        INDEX idx_certificate_usage_action (action_name)
    )""")

    # Upgrade ledgers created by the original estimate-only tracker. Existing
    # rows remain request events, while new rows contain provider-reported usage.
    for statement in (
        "ALTER TABLE certificate_usage_events ADD COLUMN event_type ENUM('request', 'model') NOT NULL DEFAULT 'request'",
        "ALTER TABLE certificate_usage_events ADD COLUMN input_tokens INT NOT NULL DEFAULT 0",
        "ALTER TABLE certificate_usage_events ADD COLUMN output_tokens INT NOT NULL DEFAULT 0",
        "ALTER TABLE certificate_usage_events ADD COLUMN total_tokens INT NOT NULL DEFAULT 0",
    ):
        try:
            cursor.execute(statement)
        except Exception:
            pass

    # ---- Admin-managed certification department/subject system ----

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS cert_departments (
        id INT PRIMARY KEY AUTO_INCREMENT,
        name VARCHAR(255) UNIQUE NOT NULL,
        description TEXT,
        is_active BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS cert_subjects (
        id INT PRIMARY KEY AUTO_INCREMENT,
        dept_id INT NOT NULL,
        name VARCHAR(255) NOT NULL,
        questions_status ENUM('pending','generating','ready','failed') DEFAULT 'pending',
        question_count INT DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE KEY unique_dept_subject (dept_id, name),
        FOREIGN KEY (dept_id) REFERENCES cert_departments(id) ON DELETE CASCADE
    )""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS cert_question_cache (
        id INT PRIMARY KEY AUTO_INCREMENT,
        subject_id INT NOT NULL,
        questions_json LONGTEXT NOT NULL,
        generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (subject_id) REFERENCES cert_subjects(id) ON DELETE CASCADE
    )""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS web_search_cache (
        id INT PRIMARY KEY AUTO_INCREMENT,
        topic VARCHAR(255) NOT NULL,
        difficulty VARCHAR(50) NOT NULL,
        questions_json LONGTEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_topic_diff (topic, difficulty)
    )""")

    # ---- Conversational Exam Session & Chat History Schema ----

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS conversation_sessions (
        id VARCHAR(36) PRIMARY KEY,
        user_id INT NOT NULL,
        topic VARCHAR(255) DEFAULT '',
        status ENUM('onboarding','calibrating','ready','in_exam','grading','completed','failed','generating','generation_failed') DEFAULT 'onboarding',
        current_question_index INT DEFAULT 0,
        total_questions INT DEFAULT 0,
        score FLOAT DEFAULT NULL,
        questions_json LONGTEXT DEFAULT NULL,
        exam_id INT DEFAULT NULL,
        certificate_id INT DEFAULT NULL,
        started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        completed_at TIMESTAMP NULL DEFAULT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (exam_id) REFERENCES exams(id) ON DELETE SET NULL,
        FOREIGN KEY (certificate_id) REFERENCES certificates(id) ON DELETE SET NULL
    )""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chat_messages (
        id VARCHAR(36) PRIMARY KEY,
        session_id VARCHAR(36) NOT NULL,
        role ENUM('user','assistant','system') NOT NULL,
        content TEXT NOT NULL,
        message_type ENUM('text','mcq_question','mcq_answer','freetext_question','freetext_answer','feedback','certificate_card','take_exam_card') DEFAULT 'text',
        metadata JSON DEFAULT NULL,
        seq INT AUTO_INCREMENT UNIQUE KEY,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (session_id) REFERENCES conversation_sessions(id) ON DELETE CASCADE
    )""")

    # Alterations to update existing tables if they were created with the older schema:
    try:
        cursor.execute("ALTER TABLE conversation_sessions ADD COLUMN questions_json LONGTEXT DEFAULT NULL")
    except Exception:
        pass

    try:
        cursor.execute("ALTER TABLE conversation_sessions ADD COLUMN exam_id INT DEFAULT NULL")
    except Exception:
        pass

    try:
        cursor.execute("ALTER TABLE conversation_sessions ADD COLUMN certificate_id INT DEFAULT NULL")
    except Exception:
        pass

    try:
        cursor.execute("ALTER TABLE conversation_sessions ADD CONSTRAINT fk_conversation_sessions_exam_id FOREIGN KEY (exam_id) REFERENCES exams(id) ON DELETE SET NULL")
    except Exception:
        pass

    try:
        cursor.execute("ALTER TABLE conversation_sessions ADD CONSTRAINT fk_conversation_sessions_certificate_id FOREIGN KEY (certificate_id) REFERENCES certificates(id) ON DELETE SET NULL")
    except Exception:
        pass

    try:
        cursor.execute("ALTER TABLE conversation_sessions MODIFY COLUMN status ENUM('onboarding','calibrating','ready','in_exam','grading','completed','failed','generating','generation_failed') DEFAULT 'onboarding'")
    except Exception:
        pass

    try:
        cursor.execute("ALTER TABLE conversation_sessions MODIFY COLUMN topic VARCHAR(255) DEFAULT ''")
    except Exception:
        pass

    try:
        cursor.execute("ALTER TABLE chat_messages ADD COLUMN seq INT AUTO_INCREMENT UNIQUE KEY")
    except Exception:
        pass

    try:
        cursor.execute("ALTER TABLE certificates MODIFY COLUMN exam_id INT NULL")
    except Exception:
        pass

    try:
        cursor.execute("ALTER TABLE certificates ADD COLUMN recipient_name VARCHAR(255) NULL")
    except Exception:
        pass

    # Preserve a stable recipient name for certificates created before this
    # field existed; a later name change only affects the selected certificate.
    try:
        cursor.execute(
            "UPDATE certificates c JOIN users u ON u.id = c.user_id "
            "SET c.recipient_name = u.name WHERE c.recipient_name IS NULL OR c.recipient_name = ''"
        )
    except Exception:
        pass

    try:
        cursor.execute("ALTER TABLE chat_messages MODIFY COLUMN message_type ENUM('text','mcq_question','mcq_answer','freetext_question','freetext_answer','feedback','certificate_card','take_exam_card') DEFAULT 'text'")
    except Exception:
        pass

    # ── Startup recovery: reset any sessions stuck in "generating" ──────────────
    # If the server restarted while a background thread was generating questions,
    # that thread is dead but the DB row is still "generating". Reset them now so
    # the frontend polling loop terminates rather than running forever.
    # Scoped to sessions > 5 min old so a rolling-restart with multiple workers
    # cannot wrongly cancel a concurrent worker's still-in-progress generation.
    try:
        cursor.execute(
            "UPDATE conversation_sessions "
            "SET status = 'generation_failed' "
            "WHERE status = 'generating' "
            "AND started_at < NOW() - INTERVAL 5 MINUTE"
        )
        recovered = cursor.rowcount
        if recovered:
            logger.warning(f"[Startup] Reset {recovered} orphaned 'generating' session(s) to 'generation_failed'.")
    except Exception:
        pass

    conn.commit()
    cursor.close()
    conn.close()
    logger.info("[OK] Database initialized successfully")


def get_cached_web_search_questions(topic: str, difficulty: str, ttl_hours: int = 24) -> Optional[List[Dict]]:
    """Look up cached web search questions for (topic, difficulty) created within ttl_hours."""
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                """SELECT questions_json FROM web_search_cache
                   WHERE LOWER(topic) = LOWER(%s) AND LOWER(difficulty) = LOWER(%s)
                   AND created_at >= NOW() - INTERVAL %s HOUR
                   ORDER BY created_at DESC LIMIT 1""",
                (topic.strip(), difficulty.strip(), ttl_hours)
            )
            row = cursor.fetchone()
            if row and row.get("questions_json"):
                return json.loads(row["questions_json"])
            return None
        finally:
            cursor.close()
            conn.close()
    except Exception as e:
        logger.warning(f"[WebSearchCache] Error reading cache from DB: {e}")
        return None


def save_cached_web_search_questions(topic: str, difficulty: str, questions: List[Dict]) -> None:
    """Save generated web search questions to web_search_cache."""
    if not questions:
        return
    try:
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """INSERT INTO web_search_cache (topic, difficulty, questions_json)
                   VALUES (%s, %s, %s)""",
                (topic.strip(), difficulty.strip(), json.dumps(questions))
            )
            conn.commit()
            logger.info(f"[WebSearchCache] Saved {len(questions)} questions for '{topic}' ({difficulty}) to cache")
        finally:
            cursor.close()
            conn.close()
    except Exception as e:
        logger.warning(f"[WebSearchCache] Error saving cache to DB: {e}")


