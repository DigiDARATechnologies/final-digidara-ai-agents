import time
import uuid
from datetime import datetime, timedelta
from threading import Event, Lock

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError

from ..extensions import db
from ..models import GeneratedTopic
from ..services import groq_service

practice_bp = Blueprint("practice", __name__)

ALLOWED_PRACTICE_TYPES = {"speaking", "writing"}
ALLOWED_MODES = {"topic_wise", "daily_conversation"}
ALLOWED_DIFFICULTIES = {"easy", "medium", "hard"}
REFRESH_SECONDS = 5
TOPIC_CACHE_SECONDS = 300
_generation_log = {}
_generation_guard = Lock()
_schema_guard = Lock()
_generation_inflight = {}
_generation_results = {}
_schema_ready = False


def _api_error(message, error_code, status=400):
    return jsonify({"success": False, "message": message, "error_code": error_code}), status


def _topic_response(payload, status=200):
    return jsonify(payload), status


def _remember_generation_result(log_key, payload, status=200):
    _generation_results[log_key] = {
        "payload": payload,
        "status": status,
        "created_at": time.time(),
    }


def _recent_generation_result(log_key):
    result = _generation_results.get(log_key)
    if not result:
        return None
    if time.time() - result["created_at"] > REFRESH_SECONDS:
        _generation_results.pop(log_key, None)
        return None
    return result


def _normalize_mode(mode):
    value = (mode or "").strip().lower()
    if value in {"topic", "topic_wise", "topic-wise"}:
        return "topic_wise"
    if value in {"daily", "daily_conversation", "daily-conversation"}:
        return "daily_conversation"
    return value


def _ensure_practice_schema():
    inspector = inspect(db.engine)
    tables = set(inspector.get_table_names())
    if "generated_topics" not in tables:
        db.session.execute(text("""
            CREATE TABLE generated_topics (
                id INT AUTO_INCREMENT PRIMARY KEY,
                public_id VARCHAR(64) NOT NULL UNIQUE,
                user_id INT NOT NULL,
                practice_type VARCHAR(20) NOT NULL,
                mode VARCHAR(30) NOT NULL,
                difficulty VARCHAR(20) NOT NULL,
                title VARCHAR(200) NOT NULL,
                description VARCHAR(500) NOT NULL,
                expected_duration_seconds INT NULL,
                minimum_word_count INT NULL,
                maximum_word_count INT NULL,
                source VARCHAR(20) NOT NULL DEFAULT 'groq',
                used_in_session BOOLEAN NOT NULL DEFAULT FALSE,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_generated_topics_user_context (user_id, practice_type, mode, difficulty, created_at),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """))

    session_alters = {
        "speaking_sessions": {
            "generated_topic_id": "ADD COLUMN generated_topic_id VARCHAR(64) NULL AFTER mode",
        },
        "writing_sessions": {
            "generated_topic_id": "ADD COLUMN generated_topic_id VARCHAR(64) NULL AFTER mode",
            "topic_description": "ADD COLUMN topic_description VARCHAR(500) NULL AFTER topic_title",
        },
    }
    for table, alters in session_alters.items():
        columns = {column["name"] for column in inspector.get_columns(table)}
        for column, ddl in alters.items():
            if column not in columns:
                db.session.execute(text(f"ALTER TABLE {table} {ddl}"))
    db.session.commit()


def _ensure_practice_schema_once():
    global _schema_ready
    if _schema_ready:
        return
    with _schema_guard:
        if _schema_ready:
            return
        _ensure_practice_schema()
        _schema_ready = True


def _recent_topic_titles(user_id, practice_type, mode, difficulty):
    rows = (
        GeneratedTopic.query.filter_by(
            user_id=user_id,
            practice_type=practice_type,
            mode=mode,
            difficulty=difficulty,
        )
        .order_by(GeneratedTopic.created_at.desc())
        .limit(10)
        .all()
    )
    return [row.title for row in rows]


def _recent_generated_topic_rows(user_id, practice_type, mode, difficulty, limit=6):
    cutoff = datetime.utcnow() - timedelta(seconds=TOPIC_CACHE_SECONDS)
    rows = (
        GeneratedTopic.query.filter_by(
            user_id=user_id,
            practice_type=practice_type,
            mode=mode,
            difficulty=difficulty,
            used_in_session=False,
        )
        .order_by(GeneratedTopic.created_at.desc())
        .limit(limit)
        .all()
    )
    fresh_rows = []
    for row in rows:
        if row.created_at and row.created_at >= cutoff:
            fresh_rows.append(row)
    return fresh_rows


def _validate_topic_request(data):
    practice_type = (data.get("practice_type") or "").strip().lower()
    mode = _normalize_mode(data.get("mode"))
    difficulty = (data.get("difficulty") or "medium").strip().lower()

    if practice_type not in ALLOWED_PRACTICE_TYPES:
        return None, _api_error("practice_type must be speaking or writing", "INVALID_PRACTICE_TYPE")
    if mode not in ALLOWED_MODES:
        return None, _api_error("mode must be topic_wise or daily_conversation", "INVALID_MODE")
    if difficulty not in ALLOWED_DIFFICULTIES:
        return None, _api_error("difficulty must be easy, medium or hard", "INVALID_DIFFICULTY")
    return (practice_type, mode, difficulty), None


def _create_generated_topic(user_id, practice_type, mode, difficulty, topic):
    generated = GeneratedTopic(
        public_id=f"generated-{uuid.uuid4().hex}",
        user_id=user_id,
        practice_type=practice_type,
        mode=mode,
        difficulty=difficulty,
        title=topic["title"],
        description=topic["description"],
        expected_duration_seconds=topic.get("expected_duration_seconds"),
        minimum_word_count=topic.get("minimum_word_count"),
        maximum_word_count=topic.get("maximum_word_count"),
        source=topic.get("source") or "groq",
    )
    db.session.add(generated)
    return generated


@practice_bp.post("/generate-topic")
@jwt_required()
def generate_topic():
    user_id = int(get_jwt_identity())
    data = request.get_json(silent=True) or {}
    validated, error = _validate_topic_request(data)
    if error:
        return error
    practice_type, mode, difficulty = validated

    log_key = f"{user_id}:{practice_type}:{mode}:{difficulty}"
    now = time.time()
    should_generate = False
    wait_for_generation = None
    with _generation_guard:
        wait_for_generation = _generation_inflight.get(log_key)
        if wait_for_generation is None:
            if now - _generation_log.get(log_key, 0) < REFRESH_SECONDS:
                return _api_error("Please wait a few seconds before generating another topic.", "RATE_LIMITED", 429)
            wait_for_generation = Event()
            _generation_inflight[log_key] = wait_for_generation
            _generation_log[log_key] = now
            should_generate = True

    if not should_generate:
        if wait_for_generation.wait(timeout=4):
            with _generation_guard:
                result = _recent_generation_result(log_key)
            if result:
                return _topic_response(result["payload"], result["status"])
        return _api_error("Topic generation is still in progress. Retrying shortly.", "GENERATION_IN_PROGRESS", 429)

    try:
        _ensure_practice_schema_once()
        recent_topics = _recent_topic_titles(user_id, practice_type, mode, difficulty)
        topic = groq_service.generate_practice_topic(practice_type, mode, difficulty, recent_topics)
        generated = _create_generated_topic(user_id, practice_type, mode, difficulty, topic)
        db.session.commit()
        payload = {"success": True, "data": generated.to_dict()}
        with _generation_guard:
            _remember_generation_result(log_key, payload)
        return jsonify(payload)
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Generated topic persistence failed")
        fallback = groq_service.fallback_practice_topic(practice_type, mode, difficulty)
        fallback["topic_id"] = f"fallback-{uuid.uuid4().hex}"
        fallback.update({
            "difficulty": difficulty,
            "practice_type": practice_type,
            "mode": mode,
        })
        payload = {"success": True, "data": fallback}
        with _generation_guard:
            _remember_generation_result(log_key, payload)
        return jsonify(payload)
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Generated topic creation failed")
        fallback = groq_service.fallback_practice_topic(practice_type, mode, difficulty)
        fallback["topic_id"] = f"fallback-{uuid.uuid4().hex}"
        fallback.update({
            "difficulty": difficulty,
            "practice_type": practice_type,
            "mode": mode,
        })
        payload = {"success": True, "data": fallback}
        with _generation_guard:
            _remember_generation_result(log_key, payload)
        return jsonify(payload)
    finally:
        with _generation_guard:
            event = _generation_inflight.pop(log_key, None)
            if event:
                event.set()


@practice_bp.post("/generate-topics")
@jwt_required()
def generate_topics():
    user_id = int(get_jwt_identity())
    data = request.get_json(silent=True) or {}
    validated, error = _validate_topic_request(data)
    if error:
        return error
    practice_type, mode, difficulty = validated

    try:
        _ensure_practice_schema_once()
        cached_rows = _recent_generated_topic_rows(user_id, practice_type, mode, difficulty, limit=6)
        if len(cached_rows) >= 6:
            return jsonify({"success": True, "data": [row.to_dict() for row in cached_rows[:6]]})
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.warning("Generated topics cache lookup failed", exc_info=True)

    log_key = f"{user_id}:{practice_type}:{mode}:{difficulty}:topics"
    now = time.time()
    should_generate = False
    wait_for_generation = None
    with _generation_guard:
        wait_for_generation = _generation_inflight.get(log_key)
        if wait_for_generation is None:
            if now - _generation_log.get(log_key, 0) < REFRESH_SECONDS:
                return _api_error("Please wait a few seconds before generating more topics.", "RATE_LIMITED", 429)
            wait_for_generation = Event()
            _generation_inflight[log_key] = wait_for_generation
            _generation_log[log_key] = now
            should_generate = True

    if not should_generate:
        if wait_for_generation.wait(timeout=6):
            with _generation_guard:
                result = _recent_generation_result(log_key)
            if result:
                return _topic_response(result["payload"], result["status"])
        return _api_error("Topic generation is still in progress. Retrying shortly.", "GENERATION_IN_PROGRESS", 429)

    try:
        recent_topics = _recent_topic_titles(user_id, practice_type, mode, difficulty)
        topics = groq_service.generate_practice_topics(practice_type, mode, difficulty, recent_topics, count=6)
        generated_rows = [
            _create_generated_topic(user_id, practice_type, mode, difficulty, topic)
            for topic in topics[:6]
        ]

        db.session.commit()
        payload = {"success": True, "data": [row.to_dict() for row in generated_rows[:6]]}
        with _generation_guard:
            _remember_generation_result(log_key, payload)
        return jsonify(payload)
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Generated topics persistence failed")
        fallback_topics = []
        for fallback in groq_service.fallback_practice_topics(practice_type, mode, difficulty, count=6):
            fallback["topic_id"] = f"fallback-{uuid.uuid4().hex}"
            fallback.update({"difficulty": difficulty, "practice_type": practice_type, "mode": mode})
            fallback_topics.append(fallback)
        payload = {"success": True, "data": fallback_topics}
        with _generation_guard:
            _remember_generation_result(log_key, payload)
        return jsonify(payload)
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Generated topics creation failed")
        fallback_topics = []
        for fallback in groq_service.fallback_practice_topics(practice_type, mode, difficulty, count=6):
            fallback["topic_id"] = f"fallback-{uuid.uuid4().hex}"
            fallback.update({"difficulty": difficulty, "practice_type": practice_type, "mode": mode})
            fallback_topics.append(fallback)
        payload = {"success": True, "data": fallback_topics}
        with _generation_guard:
            _remember_generation_result(log_key, payload)
        return jsonify(payload)
    finally:
        with _generation_guard:
            event = _generation_inflight.pop(log_key, None)
            if event:
                event.set()
