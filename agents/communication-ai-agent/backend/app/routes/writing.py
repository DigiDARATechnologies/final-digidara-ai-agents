import json
import difflib
from datetime import datetime, timedelta

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError

from ..extensions import db, limiter
from ..models import GeneratedTopic, Topic, WritingSession, WritingTurn
from ..services import groq_service
from ..services.daily_challenges import (
    ACTIVITY_CONFIG,
    WRITING_DAILY,
    activity_status,
    backfill_today_from_completed_sessions,
    challenge_day_bounds,
    complete_daily_activity,
    mark_activity_started,
    today_challenge_date,
    today_status,
)
from ..utils.score_utils import convert_scores_dict, to_score10

writing_bp = Blueprint("writing", __name__)

DEFAULT_OPEN_ENDED_TURNS = 0
ALLOWED_DIFFICULTIES = {"easy", "medium", "hard"}
DEFAULT_WRITING_TOPICS = {
    "easy": {
        "Favorite Hobby": "Write about a hobby and why you enjoy it",
        "My Daily Routine": "Write about a normal day in your life",
        "My Best Friend": "Describe a close friend",
        "My Favourite Food": "Write about food you enjoy",
    },
    "medium": {
        "Social Media Impact": "Write about how social media affects society",
        "Remote Work": "Write about the pros and cons of working from home",
        "Time Management": "Explain how people can manage time better",
        "Learning New Skills": "Write about how you learn something new",
    },
    "hard": {
        "Education System": "Write about strengths and weaknesses of education today",
        "Future of Cities": "Write about how cities might change in the future",
        "Impact of Artificial Intelligence": "Analyze how AI affects work and society",
        "Ethical Challenges in Technology": "Write about responsibility in technology",
    },
}


def _avg(*values):
    values = [v for v in values if v is not None]
    return round(sum(values) / len(values), 1) if values else None


def _api_error(message, error_code, status=400):
    return jsonify({"success": False, "message": message, "error_code": error_code}), status


def _normalize_start_mode(mode):
    value = (mode or "").strip().lower()
    if value in {"topic", "topic_wise", "topic-wise"}:
        return "topic"
    if value in {"daily", "daily_conversation", "daily-conversation"}:
        return "daily"
    return value


def _normalize_weak_area_tag(value):
    tag = " ".join(str(value or "").strip().lower().replace("_", " ").replace("-", " ").split())
    if not tag:
        return None
    mappings = (
        ("subject", "verb", "subject-verb agreement"),
        ("tense", None, "tense error"),
        ("article", None, "article usage"),
        ("preposition", None, "preposition"),
        ("punctuation", None, "punctuation"),
        ("spelling", None, "spelling"),
        ("word choice", None, "word choice"),
        ("vocabulary", None, "word choice"),
        ("sentence structure", None, "sentence structure"),
        ("fragment", None, "sentence structure"),
        ("clarity", None, "clarity"),
    )
    for first, second, normalized in mappings:
        if first in tag and (second is None or second in tag):
            return normalized
    return tag[:80]


def _weak_area_tags_from_feedback(feedback):
    tags = []
    for mistake in feedback.get("mistakes", []) if isinstance(feedback, dict) else []:
        if not isinstance(mistake, dict):
            continue
        tag = _normalize_weak_area_tag(mistake.get("type"))
        if tag and tag not in tags:
            tags.append(tag)
    return tags[:5]


def _ensure_writing_schema():
    inspector = inspect(db.engine)
    session_columns = {column["name"] for column in inspector.get_columns("writing_sessions")}
    turn_columns = {column["name"] for column in inspector.get_columns("writing_turns")}
    alters = {
        "generated_topic_id": "ADD COLUMN generated_topic_id VARCHAR(64) NULL AFTER mode",
        "topic_description": "ADD COLUMN topic_description VARCHAR(500) NULL AFTER topic_title",
        "strengths_json": "ADD COLUMN strengths_json TEXT NULL AFTER summary_feedback",
        "weaknesses_json": "ADD COLUMN weaknesses_json TEXT NULL AFTER strengths_json",
        "common_mistakes_json": "ADD COLUMN common_mistakes_json TEXT NULL AFTER weaknesses_json",
        "recommendation": "ADD COLUMN recommendation TEXT NULL AFTER common_mistakes_json",
        "next_practice_suggestion": "ADD COLUMN next_practice_suggestion TEXT NULL AFTER recommendation",
    }
    turn_alters = {
        "overall_score": "ADD COLUMN overall_score FLOAT NULL AFTER knowledge_score",
        "corrected_answer": "ADD COLUMN corrected_answer TEXT NULL AFTER user_response",
        "better_natural_answer": "ADD COLUMN better_natural_answer TEXT NULL AFTER corrected_answer",
        "feedback_json": "ADD COLUMN feedback_json TEXT NULL AFTER better_natural_answer",
        "draft_text": "ADD COLUMN draft_text TEXT NULL AFTER feedback",
        "draft_updated_at": "ADD COLUMN draft_updated_at DATETIME NULL AFTER draft_text",
        "used_ai_suggestion": "ADD COLUMN used_ai_suggestion BOOLEAN DEFAULT FALSE",
        "weak_area_tags": "ADD COLUMN weak_area_tags TEXT NULL AFTER used_ai_suggestion",
        "completed_at": "ADD COLUMN completed_at DATETIME NULL AFTER weak_area_tags",
    }
    for column, ddl in alters.items():
        if column not in session_columns:
            db.session.execute(text(f"ALTER TABLE writing_sessions {ddl}"))
    for column, ddl in turn_alters.items():
        if column not in turn_columns:
            db.session.execute(text(f"ALTER TABLE writing_turns {ddl}"))
    db.session.commit()


def _ensure_default_topic(topic_title, difficulty):
    description = DEFAULT_WRITING_TOPICS.get(difficulty, {}).get(topic_title)
    if not description:
        return None

    topic = Topic.query.filter_by(category="writing", title=topic_title).first()
    if topic:
        topic.description = description
        topic.difficulty = difficulty
        return topic

    topic = Topic(category="writing", title=topic_title, description=description, difficulty=difficulty)
    db.session.add(topic)
    db.session.flush()
    return topic


def _turn_payload(turn):
    return turn.to_dict()


def _session_payload(session):
    current_turn = next((turn for turn in session.turns if not turn.user_response), None)
    total_turns = session.total_turns or DEFAULT_OPEN_ENDED_TURNS
    return {
        "success": True,
        "session_id": session.id,
        "turn_number": current_turn.turn_number if current_turn else len(session.turns) + 1,
        "turn_id": current_turn.id if current_turn else None,
        "total_turns": total_turns,
        "prompt": current_turn.ai_prompt if current_turn else None,
        "draft_text": current_turn.draft_text if current_turn else "",
        "draft_updated_at": current_turn.draft_updated_at.isoformat() if current_turn and current_turn.draft_updated_at else None,
        "mode": session.mode,
        "difficulty": session.difficulty,
        "generated_topic_id": session.generated_topic_id,
        "topic_title": session.topic_title,
        "topic_description": session.topic_description,
        "status": session.status,
        "turns": [_turn_payload(turn) for turn in session.turns],
    }


def _finalize_writing_session(session, mark_daily_completion=False, result_id=None):
    turns = [turn for turn in session.turns if turn.user_response]
    session.total_turns = len(turns)
    session.grammar_score = _avg(*[t.grammar_score for t in turns])
    session.vocabulary_score = _avg(*[t.vocabulary_score for t in turns])
    session.clarity_score = _avg(*[t.clarity_score for t in turns])
    session.knowledge_score = _avg(*[t.knowledge_score for t in turns]) if session.mode == "topic" else None
    session.overall_score = _avg(
        session.grammar_score, session.vocabulary_score, session.clarity_score, session.knowledge_score
    )
    session.status = "completed"
    session.completed_at = datetime.utcnow()

    if turns:
        try:
            summary = groq_service.summarize_writing_session(
                session.mode, session.topic_title, [t.to_dict() for t in turns]
            )
            if not isinstance(summary, dict) or not summary.get("summary_feedback"):
                raise ValueError("Malformed writing session summary")
        except Exception:
            current_app.logger.exception("Writing session summary generation failed")
            summary = {
                "summary_feedback": "Your writing session is complete. Review your scores and keep practicing.",
                "strengths": [],
                "areas_to_improve": [],
                "common_mistakes": [],
                "recommendation": "Keep practicing with a new writing prompt.",
                "next_practice_suggestion": "Try another writing session.",
            }
    else:
        summary = {
            "summary_feedback": "The writing session ended before any answers were submitted.",
            "strengths": [],
            "areas_to_improve": ["Try one complete answer in the next session."],
            "common_mistakes": [],
            "recommendation": "Start a new writing session when you are ready.",
            "next_practice_suggestion": "Try one short, clear paragraph.",
        }

    session.summary_feedback = summary["summary_feedback"]
    session.strengths_json = json.dumps(summary.get("strengths", []))
    session.weaknesses_json = json.dumps(summary.get("areas_to_improve", []))
    session.common_mistakes_json = json.dumps(summary.get("common_mistakes", []))
    session.recommendation = summary.get("recommendation")
    session.next_practice_suggestion = summary.get("next_practice_suggestion")

    if mark_daily_completion and session.mode == "daily":
        complete_daily_activity(session.user_id, WRITING_DAILY, session.id, result_id=result_id)

    return summary


def _create_or_restore_daily_writing_session(user_id, difficulty, mark_started=False):
    start_utc, end_utc = challenge_day_bounds()
    existing = (
        WritingSession.query.filter(
            WritingSession.user_id == user_id,
            WritingSession.mode == "daily",
            WritingSession.created_at >= start_utc,
            WritingSession.created_at <= end_utc,
            WritingSession.status.in_(["in_progress", "completed"]),
        )
        .order_by(WritingSession.created_at.desc())
        .first()
    )
    if existing:
        if mark_started and existing.status == "in_progress":
            mark_activity_started(user_id, WRITING_DAILY, session_id=existing.id)
        return existing, False

    session = WritingSession(
        user_id=user_id,
        mode="daily",
        topic_title="Daily Writing",
        topic_description="Today's assigned daily writing challenge.",
        difficulty=difficulty,
        status="in_progress",
        total_turns=DEFAULT_OPEN_ENDED_TURNS,
    )
    db.session.add(session)
    db.session.flush()

    prompt = groq_service.generate_writing_prompt(
        "daily",
        difficulty,
        session.topic_title,
        1,
        [],
        topic_description=session.topic_description,
    )
    db.session.add(WritingTurn(session_id=session.id, turn_number=1, ai_prompt=prompt))
    if mark_started:
        mark_activity_started(user_id, WRITING_DAILY, session_id=session.id)
    return session, True


def check_duplicate_submission(user_id, text):
    if not text or len(text.strip()) < 20:
        return False
    recent_turns = (
        WritingTurn.query.join(WritingSession)
        .filter(WritingSession.user_id == user_id)
        .order_by(WritingTurn.created_at.desc())
        .limit(10)
        .all()
    )
    for turn in recent_turns:
        if turn.user_response and len(turn.user_response) >= 20:
            similarity = difflib.SequenceMatcher(None, text.lower(), turn.user_response.lower()).ratio()
            if similarity > 0.85:
                return True
    return False


@writing_bp.post("/tone")
@limiter.limit("30 per minute")
@jwt_required()
def tone_check():
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    result = groq_service.detect_tone(text)
    return jsonify({"success": True, "tone": result["tone"], "confidence": result["confidence"], "source": result["source"]})


@writing_bp.post("/quick-check")
@limiter.limit("45 per minute")
@jwt_required()
def quick_check():
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    if len(text) < 15:
        return jsonify({"issues": []})
    return jsonify(groq_service.quick_grammar_check(text))


@writing_bp.post("/live-check")
@limiter.limit("30 per minute")
@jwt_required()
def live_check():
    user_id = int(get_jwt_identity())
    data = request.get_json(silent=True) or {}
    text = data.get("text") or data.get("draft_text") or ""
    difficulty = (data.get("difficulty") or "easy").strip().lower()
    mode = _normalize_start_mode(data.get("mode")) or "topic"
    prompt = (data.get("prompt") or "")[:500]
    if difficulty not in ALLOWED_DIFFICULTIES:
        return _api_error("difficulty must be easy, medium or hard", "INVALID_DIFFICULTY")
    if mode not in ("topic", "daily"):
        return _api_error("mode must be 'topic' or 'daily'", "INVALID_MODE")
    if len(text) > 10000:
        return _api_error("Draft is too long. Please keep it under 10000 characters.", "DRAFT_TOO_LONG")
    if len(text.strip()) < 8:
        return jsonify({"success": True, "issues": [], "grade": None, "tone": "neutral", "confidence": 0.0, "is_duplicate": False, "source": "fallback"})
    try:
        is_duplicate = check_duplicate_submission(user_id, text)
        result = groq_service.live_writing_insights(
            text,
            difficulty=difficulty,
            mode=mode,
            prompt=prompt,
            is_duplicate=is_duplicate,
        )
    except Exception:
        current_app.logger.exception("Live writing check failed")
        result = {
            "issues": [],
            "grade": None,
            "tone": "neutral",
            "confidence": 0.0,
            "is_duplicate": is_duplicate if "is_duplicate" in locals() else False,
            "source": "fallback",
        }
    return jsonify({"success": True, **result})


@writing_bp.post("/check_duplicate")
@limiter.limit("30 per minute")
@jwt_required()
def duplicate_check():
    user_id = int(get_jwt_identity())
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    is_duplicate = check_duplicate_submission(user_id, text)
    return jsonify({"success": True, "is_duplicate": is_duplicate})


@writing_bp.get("/topics")
@jwt_required()
def list_topics():
    difficulty = (request.args.get("difficulty") or "").strip().lower()
    if difficulty and difficulty not in ALLOWED_DIFFICULTIES:
        return jsonify({"message": "difficulty must be easy, medium or hard"}), 400
    query = Topic.query.filter_by(category="writing")
    if difficulty:
        query = query.filter_by(difficulty=difficulty)
    topics = query.all()
    return jsonify({"topics": [t.to_dict() for t in topics]})


@writing_bp.post("/rewrite/generate")
@jwt_required()
def generate_rewrite_sentence():
    data = request.get_json(silent=True) or {}
    difficulty = (data.get("difficulty") or "medium").strip().lower()
    if difficulty not in ALLOWED_DIFFICULTIES:
        return _api_error("difficulty must be easy, medium or hard", "INVALID_DIFFICULTY")
    item = groq_service.generate_sentence_rewrite_prompt(difficulty)
    return jsonify({"success": True, "data": item})


@writing_bp.post("/rewrite/evaluate")
@limiter.limit(lambda: current_app.config["ANSWER_RATE_LIMIT"])
@jwt_required()
def evaluate_rewrite_sentence():
    data = request.get_json(silent=True) or {}
    difficulty = (data.get("difficulty") or "medium").strip().lower()
    original_sentence = (data.get("original_sentence") or "").strip()
    student_rewrite = (data.get("rewrite") or data.get("answer") or "").strip()

    if difficulty not in ALLOWED_DIFFICULTIES:
        return _api_error("difficulty must be easy, medium or hard", "INVALID_DIFFICULTY")
    if not original_sentence:
        return _api_error("Rewrite sentence is missing. Generate a sentence first.", "MISSING_SENTENCE")
    if not student_rewrite:
        return _api_error("Please type your rewritten sentence before submitting.", "EMPTY_REWRITE")
    if len(original_sentence) > 1000 or len(student_rewrite) > 1000:
        return _api_error("Sentence is too long. Please keep it under 1000 characters.", "REWRITE_TOO_LONG")

    try:
        feedback = groq_service.evaluate_sentence_rewrite(difficulty, original_sentence, student_rewrite)
        if not isinstance(feedback, dict):
            raise TypeError("Sentence rewrite evaluator returned a non-object response")
        scores = feedback.get("scores") if isinstance(feedback.get("scores"), dict) else {}
        return jsonify({
            "success": True,
            "data": {
                **feedback,
                "scores": convert_scores_dict(scores),
                "grammar": to_score10(scores.get("grammar")),
                "vocabulary": to_score10(scores.get("vocabulary")),
                "clarity": to_score10(scores.get("clarity")),
                "naturalness": to_score10(scores.get("naturalness")),
                "overall": to_score10(scores.get("overall")),
            },
        })
    except Exception:
        current_app.logger.exception("Sentence rewrite evaluation failed")
        return _api_error(
            "We could not evaluate this rewrite right now. Your answer was not lost; please try again.",
            "REWRITE_EVALUATION_FAILED",
            503,
        )


@writing_bp.get("/daily")
@jwt_required()
def daily_writing_challenge():
    user_id = int(get_jwt_identity())
    difficulty = (request.args.get("difficulty") or "easy").strip().lower()
    if difficulty not in ALLOWED_DIFFICULTIES:
        return _api_error("difficulty must be easy, medium or hard", "INVALID_DIFFICULTY")
    try:
        _ensure_writing_schema()
        session, created = _create_or_restore_daily_writing_session(user_id, difficulty)
        payload = _session_payload(session)
        daily_state = today_status(user_id)
        writing_activity = next(
            (activity for activity in daily_state["activities"] if activity["activity_type"] == WRITING_DAILY),
            None,
        )
        db.session.commit()
        return jsonify({
            "success": True,
            "challenge_date": today_challenge_date().isoformat(),
            "created": created,
            "xp_reward": ACTIVITY_CONFIG[WRITING_DAILY]["xp_reward"],
            "completed": session.status == "completed",
            "challenge_status": writing_activity["status"] if writing_activity else "not_started",
            "xp_awarded": writing_activity["xp_awarded"] if writing_activity else 0,
            "challenge": payload,
        })
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Daily writing challenge database load failed")
        return _api_error("Today's writing challenge could not be loaded right now.", "DAILY_WRITING_UNAVAILABLE", 503)
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Daily writing challenge load failed")
        return _api_error("Today's writing challenge could not be loaded right now.", "DAILY_WRITING_UNAVAILABLE", 503)


@writing_bp.get("/daily-challenge-status")
@jwt_required()
def daily_challenge_status():
    user_id = int(get_jwt_identity())
    try:
        backfill_today_from_completed_sessions(user_id)
        payload = activity_status(user_id, WRITING_DAILY)
        db.session.commit()
        return jsonify(payload)
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Writing daily challenge status query failed")
        return _api_error("Today's writing challenge status could not be loaded right now.", "DAILY_CHALLENGE_STATUS_UNAVAILABLE", 503)


@writing_bp.post("/start")
@jwt_required()
def start_session():
    user_id = int(get_jwt_identity())
    data = request.get_json(silent=True) or {}

    mode = _normalize_start_mode(data.get("mode"))
    difficulty = (data.get("difficulty") or "medium").strip().lower()
    generated_topic_id = data.get("generated_topic_id")
    topic_source = (data.get("topic_source") or "").strip().lower()
    topic_title = (data.get("topic_title") or "").strip()
    topic_description = (data.get("topic_description") or "").strip()

    if mode not in ("topic", "daily"):
        return _api_error("mode must be 'topic' or 'daily'", "INVALID_MODE")
    if difficulty not in ALLOWED_DIFFICULTIES:
        return _api_error("difficulty must be easy, medium or hard", "INVALID_DIFFICULTY")
    if mode == "topic":
        topic = None
        if topic_source == "custom":
            if len(topic_title) < 3 or len(topic_title) > 120:
                return _api_error("Custom writing topic title must be 3 to 120 characters.", "INVALID_CUSTOM_TOPIC")
            if len(topic_description) < 10 or len(topic_description) > 500:
                return _api_error("Custom writing topic instruction must be 10 to 500 characters.", "INVALID_CUSTOM_TOPIC")
        elif generated_topic_id and topic_title:
            if len(topic_title) > 120:
                return _api_error("The generated writing topic title is too long.", "INVALID_TOPIC")
            if not topic_description:
                return _api_error("The generated writing topic needs an instruction.", "INVALID_TOPIC")
            if len(topic_description) > 500:
                return _api_error("The generated writing topic instruction is too long.", "INVALID_TOPIC")
        else:
            topic = Topic.query.filter_by(category="writing", title=topic_title, difficulty=difficulty).first()
        if topic_source != "custom" and not generated_topic_id and not topic and topic_title:
            topic = _ensure_default_topic(topic_title, difficulty)
        if topic_source != "custom" and not generated_topic_id and not topic:
            return _api_error("Choose a valid writing topic for the selected difficulty.", "TOPIC_NOT_FOUND")
        if topic:
            topic_title = topic.title
            topic_description = topic.description or topic_description
    elif generated_topic_id and topic_title:
        if len(topic_title) > 120:
            return _api_error("The generated daily writing situation title is too long.", "INVALID_TOPIC")
        if topic_description and len(topic_description) > 500:
            return _api_error("The generated daily writing instruction is too long.", "INVALID_TOPIC")
    else:
        topic_title = "Daily Writing"

    try:
        _ensure_writing_schema()
    except SQLAlchemyError:
        db.session.rollback()
        return _api_error("The writing database schema is not ready.", "DATABASE_SCHEMA_OUTDATED", 503)

    if mode == "daily":
        try:
            session, created = _create_or_restore_daily_writing_session(user_id, difficulty, mark_started=True)
            payload = _session_payload(session)
            db.session.commit()
            return jsonify({**payload, "restored": not created}), 200 if not created else 201
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Could not start daily writing challenge")
            return _api_error("Today's writing challenge could not be started right now.", "DAILY_WRITING_UNAVAILABLE", 503)

    session = WritingSession(
        user_id=user_id,
        mode=mode,
        generated_topic_id=generated_topic_id,
        topic_title=topic_title,
        topic_description=topic_description or None,
        difficulty=difficulty,
        status="in_progress",
        total_turns=DEFAULT_OPEN_ENDED_TURNS,
    )
    db.session.add(session)
    db.session.flush()

    prompt = groq_service.generate_writing_prompt(mode, difficulty, topic_title, 1, [], topic_description=topic_description)

    turn = WritingTurn(session_id=session.id, turn_number=1, ai_prompt=prompt)
    db.session.add(turn)
    if mode == "daily":
        mark_activity_started(user_id, WRITING_DAILY, session_id=session.id)
    if generated_topic_id:
        GeneratedTopic.query.filter_by(public_id=generated_topic_id, user_id=user_id).update({"used_in_session": True})
    db.session.commit()

    return jsonify({
        "session_id": session.id,
        "turn_id": turn.id,
        "turn_number": 1,
        "total_turns": DEFAULT_OPEN_ENDED_TURNS,
        "prompt": prompt,
        "mode": mode,
        "difficulty": difficulty,
        "generated_topic_id": generated_topic_id,
        "topic_title": session.topic_title,
        "topic_description": session.topic_description,
    }), 201


@writing_bp.post("/chat")
@jwt_required()
def writing_chat():
    """A lightweight topic conversation, intentionally separate from scored writing turns."""
    data = request.get_json(silent=True) or {}
    topic = str(data.get("topic") or "").strip()
    difficulty = str(data.get("difficulty") or "medium").strip().lower()
    history = data.get("history") if isinstance(data.get("history"), list) else []
    if len(topic) < 3 or len(topic) > 120:
        return _api_error("Please enter a valid writing topic.", "INVALID_CUSTOM_TOPIC")
    if difficulty not in ALLOWED_DIFFICULTIES:
        return _api_error("difficulty must be easy, medium or hard", "INVALID_DIFFICULTY")
    sanitized_history = []
    for item in history[-8:]:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "").strip().lower()
        message = str(item.get("text") or "").strip()
        if role in {"assistant", "user"} and message:
            sanitized_history.append({"role": role, "text": message[:1500]})
    try:
        result = groq_service.generate_writing_chat_reply(topic, difficulty, sanitized_history)
        if not isinstance(result, dict):
            result = {"reply": str(result or ""), "corrected_answer": None}
        return jsonify({"success": True, "reply": result.get("reply"), "reaction": result.get("reaction"), "next_question": result.get("next_question"), "corrected_answer": result.get("corrected_answer")})
    except Exception:
        current_app.logger.exception("Writing chat reply failed")
        return _api_error("The writing chat is unavailable right now. Please try again.", "WRITING_CHAT_UNAVAILABLE", 503)


@writing_bp.put("/draft")
@jwt_required()
def save_draft():
    user_id = int(get_jwt_identity())
    try:
        _ensure_writing_schema()
    except SQLAlchemyError:
        db.session.rollback()
        return _api_error("The writing database schema is not ready.", "DATABASE_SCHEMA_OUTDATED", 503)
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id")
    turn_id = data.get("turn_id")
    draft_text = data.get("draft_text") or data.get("answer") or ""
    if len(draft_text) > 10000:
        return _api_error("Draft is too long. Please keep it under 10000 characters.", "DRAFT_TOO_LONG")
    session = WritingSession.query.filter_by(id=session_id, user_id=user_id, status="in_progress").first_or_404()
    turn = WritingTurn.query.filter_by(id=turn_id, session_id=session.id).first_or_404()
    if turn.user_response:
        return _api_error("This prompt has already been submitted.", "TURN_ALREADY_SUBMITTED")
    turn.draft_text = draft_text
    turn.draft_updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify({
        "success": True,
        "turn_id": turn.id,
        "draft_text": turn.draft_text,
        "draft_updated_at": turn.draft_updated_at.isoformat(),
    })


@writing_bp.delete("/draft")
@jwt_required()
def clear_draft():
    user_id = int(get_jwt_identity())
    try:
        _ensure_writing_schema()
    except SQLAlchemyError:
        db.session.rollback()
        return _api_error("The writing database schema is not ready.", "DATABASE_SCHEMA_OUTDATED", 503)
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id")
    turn_id = data.get("turn_id")
    session = WritingSession.query.filter_by(id=session_id, user_id=user_id, status="in_progress").first_or_404()
    turn = WritingTurn.query.filter_by(id=turn_id, session_id=session.id).first_or_404()
    turn.draft_text = None
    turn.draft_updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify({"success": True, "turn_id": turn.id})


@writing_bp.post("/turn/<int:turn_id>/flag_ai")
@jwt_required()
def flag_ai_suggestion(turn_id):
    user_id = int(get_jwt_identity())
    turn = WritingTurn.query.join(WritingSession).filter(
        WritingTurn.id == turn_id,
        WritingSession.user_id == user_id
    ).first_or_404()
    turn.used_ai_suggestion = True
    db.session.commit()
    return jsonify({"success": True})


@writing_bp.post("/mark-suggestion-used")
@jwt_required()
def mark_suggestion_used():
    user_id = int(get_jwt_identity())
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id")
    turn_id = data.get("turn_id")
    turn = WritingTurn.query.join(WritingSession).filter(
        WritingTurn.id == turn_id,
        WritingTurn.session_id == session_id,
        WritingSession.user_id == user_id,
    ).first_or_404()
    turn.used_ai_suggestion = True
    db.session.commit()
    return jsonify({"success": True})


@writing_bp.post("/hint")
@limiter.limit(lambda: current_app.config["ANSWER_RATE_LIMIT"])
@jwt_required()
def writing_hint():
    user_id = int(get_jwt_identity())
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id")
    turn_id = data.get("turn_id")
    current_app.logger.info(
        "Hint requested: user=%s session_id=%s turn_id=%s",
        user_id,
        session_id,
        turn_id,
    )
    answer = (data.get("answer") or "").strip()
    try:
        hint_count = max(0, min(int(data.get("hint_count") or 0), 2))
    except (TypeError, ValueError):
        hint_count = 0
    session = WritingSession.query.filter_by(id=session_id, user_id=user_id, status="in_progress").first_or_404()
    turn = WritingTurn.query.filter_by(id=turn_id, session_id=session.id).first_or_404()
    if turn.user_response:
        current_app.logger.info("Hint blocked: turn already submitted")
        return _api_error("This prompt has already been submitted.", "TURN_ALREADY_SUBMITTED")
    if hint_count >= 2:
        current_app.logger.info("Hint blocked: limit reached")
        return _api_error("You have already used both hints for this prompt.", "HINT_LIMIT_REACHED")
    hint = groq_service.generate_writing_hint(
        session.mode,
        session.difficulty,
        session.topic_title,
        session.topic_description,
        turn.ai_prompt,
        answer,
        hint_count,
    )
    current_app.logger.info("Hint generated successfully: source=%s", hint.get("source"))
    return jsonify({"success": True, "hint": hint, "hint_count": hint_count + 1, "max_hints": 2})


@writing_bp.get("/active")
@jwt_required()
def active_session():
    user_id = int(get_jwt_identity())
    try:
        _ensure_writing_schema()
    except SQLAlchemyError:
        db.session.rollback()
        return _api_error("The writing database schema is not ready.", "DATABASE_SCHEMA_OUTDATED", 503)
    session = (
        WritingSession.query.filter_by(user_id=user_id, status="in_progress")
        .order_by(WritingSession.created_at.desc())
        .first()
    )
    if not session:
        return jsonify({"success": True, "session": None})
    return jsonify({"success": True, "session": _session_payload(session)})


@writing_bp.get("/session/<int:session_id>")
@jwt_required()
def get_session(session_id):
    user_id = int(get_jwt_identity())
    try:
        _ensure_writing_schema()
    except SQLAlchemyError:
        db.session.rollback()
        return _api_error("The writing database schema is not ready.", "DATABASE_SCHEMA_OUTDATED", 503)
    session = WritingSession.query.filter_by(id=session_id, user_id=user_id).first_or_404()
    return jsonify({"success": True, "session": _session_payload(session)})


@writing_bp.get("/insights")
@jwt_required()
def writing_insights():
    user_id = int(get_jwt_identity())
    try:
        days = max(1, min(int(request.args.get("days", 30)), 365))
    except (TypeError, ValueError):
        days = 30
    cutoff = datetime.utcnow() - timedelta(days=days)
    turns = (
        WritingTurn.query.join(WritingSession)
        .filter(
            WritingSession.user_id == user_id,
            WritingTurn.completed_at >= cutoff,
            WritingTurn.weak_area_tags.isnot(None),
        )
        .all()
    )
    tag_counts = {}
    for turn in turns:
        try:
            tags = json.loads(turn.weak_area_tags or "[]")
        except (TypeError, json.JSONDecodeError):
            tags = []
        if not isinstance(tags, list):
            continue
        for tag in tags:
            normalized = _normalize_weak_area_tag(tag)
            if normalized:
                tag_counts[normalized] = tag_counts.get(normalized, 0) + 1
    weak_areas = [
        {"tag": tag, "count": count}
        for tag, count in sorted(tag_counts.items(), key=lambda item: item[1], reverse=True)[:5]
    ]
    return jsonify({"success": True, "weak_areas": weak_areas})


@writing_bp.post("/respond")
@limiter.limit(lambda: current_app.config["ANSWER_RATE_LIMIT"])
@jwt_required()
def respond():
    user_id = int(get_jwt_identity())
    try:
        _ensure_writing_schema()
    except SQLAlchemyError:
        db.session.rollback()
        return _api_error("The writing database schema is not ready.", "DATABASE_SCHEMA_OUTDATED", 503)
    data = request.get_json(silent=True) or {}

    session_id = data.get("session_id")
    answer = (data.get("answer") or "").strip()
    finalize_after_submission = bool(data.get("finalize_after_submission"))
    if not answer:
        return _api_error("Please type your answer before submitting.", "EMPTY_ANSWER")

    session = WritingSession.query.filter_by(id=session_id, user_id=user_id).first_or_404()
    if session.status != "in_progress":
        return jsonify({"message": "This session has already ended"}), 400

    try:
        if not session.turns:
            return _api_error("No active prompt found for this session.", "NO_ACTIVE_TURN", 400)
        current_turn = next((turn for turn in session.turns if not turn.user_response), None)
        if current_turn is None:
            return _api_error("This prompt has already been submitted.", "TURN_ALREADY_SUBMITTED", 409)
        current_turn.user_response = answer
        current_turn.used_ai_suggestion = bool(data.get("used_ai_suggestion"))
        current_turn.draft_text = None
        current_turn.draft_updated_at = datetime.utcnow()
        current_turn.completed_at = datetime.utcnow()

        feedback = groq_service.evaluate_writing_answer(
            session.mode, session.difficulty, session.topic_title, current_turn.ai_prompt, current_turn.user_response
        )
        feedback = feedback if isinstance(feedback, dict) else {}
        scores = feedback.get("scores") if isinstance(feedback.get("scores"), dict) else {}
        current_turn.grammar_score = scores.get("grammar")
        current_turn.vocabulary_score = scores.get("vocabulary")
        current_turn.clarity_score = scores.get("clarity")
        current_turn.knowledge_score = scores.get("knowledge")
        current_turn.overall_score = scores.get("overall")
        current_turn.corrected_answer = feedback.get("corrected_answer") or answer
        current_turn.better_natural_answer = feedback.get("better_natural_answer") or current_turn.corrected_answer
        current_turn.feedback_json = json.dumps(feedback)
        current_turn.feedback = feedback.get("short_feedback") or feedback.get("feedback") or "Your answer was received."
        current_turn.weak_area_tags = json.dumps(_weak_area_tags_from_feedback(feedback))

        if session.mode == "daily":
            complete_daily_activity(user_id, WRITING_DAILY, session.id, result_id=current_turn.id)

        next_turn = None
        next_prompt = None
        next_turn_number = current_turn.turn_number
        if not finalize_after_submission:
            history = [{"question": t.ai_prompt, "answer": t.user_response} for t in session.turns]
            next_turn_number = current_turn.turn_number + 1
            next_prompt = groq_service.generate_writing_prompt(
                session.mode, session.difficulty, session.topic_title, next_turn_number, history,
                topic_description=session.topic_description,
            )
            next_turn = WritingTurn(session_id=session.id, turn_number=next_turn_number, ai_prompt=next_prompt)
            db.session.add(next_turn)
        db.session.commit()

        return jsonify({
            "done": finalize_after_submission,
            "session_id": session.id,
            "turn_id": next_turn.id if next_turn else None,
            "submitted_turn_id": current_turn.id,
            "turn_number": next_turn_number,
            "total_turns": session.total_turns or DEFAULT_OPEN_ENDED_TURNS,
            "prompt": next_prompt,
            "feedback": feedback,
            "last_turn_scores": {
                **feedback,
                **convert_scores_dict(scores),
                "scores": convert_scores_dict(scores),
                "feedback": current_turn.feedback,
            },
        })
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Writing answer persistence failed")
        return _api_error("Could not save your answer. Please try again.", "DATABASE_ERROR", 503)
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Writing answer evaluation failed")
        return _api_error("Something went wrong evaluating your answer. Please try submitting again.", "EVALUATION_FAILED", 500)


@writing_bp.post("/end")
@jwt_required()
def end_session():
    user_id = int(get_jwt_identity())
    try:
        _ensure_writing_schema()
    except SQLAlchemyError:
        db.session.rollback()
        return _api_error("The writing database schema is not ready.", "DATABASE_SCHEMA_OUTDATED", 503)
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id")
    session = WritingSession.query.filter_by(id=session_id, user_id=user_id).first_or_404()

    if session.status != "in_progress":
        return jsonify({"success": True, "done": True, "session_id": session.id, "summary": session.to_detail_dict()})

    try:
        summary = _finalize_writing_session(session, mark_daily_completion=session.mode == "daily")
        db.session.commit()
        return jsonify({
            "success": True,
            "done": True,
            "session_id": session.id,
            "overall_score": to_score10(session.overall_score),
            "grammar_score": to_score10(session.grammar_score),
            "vocabulary_score": to_score10(session.vocabulary_score),
            "clarity_score": to_score10(session.clarity_score),
            "knowledge_score": to_score10(session.knowledge_score),
            "summary": session.summary_feedback,
            "summary_feedback": session.summary_feedback,
            "strengths": summary.get("strengths", []),
            "areas_to_improve": summary.get("areas_to_improve", []),
            "common_mistakes": summary.get("common_mistakes", []),
            "recommendation": summary.get("recommendation"),
            "next_practice_suggestion": summary.get("next_practice_suggestion"),
            "turns": [t.to_dict() for t in session.turns if t.user_response],
        })
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Writing session end failed")
        return _api_error("Could not end the writing session. Please try again.", "DATABASE_ERROR", 503)


@writing_bp.get("/progress")
@jwt_required()
def writing_progress():
    user_id = int(get_jwt_identity())
    sessions = (
        WritingSession.query.filter(
            WritingSession.user_id == user_id,
            WritingSession.status == "completed",
            WritingSession.overall_score.isnot(None),
            WritingSession.completed_at.isnot(None),
        )
        .order_by(WritingSession.completed_at.asc())
        .limit(30)
        .all()
    )
    scores = [to_score10(session.overall_score) for session in sessions]
    scores = [score for score in scores if score is not None]
    return jsonify({
        "success": True,
        "average": round(sum(scores) / len(scores), 1) if scores else None,
        "completed": len(scores),
        "best": max(scores) if scores else None,
        "progress": [
            {
                "date": session.completed_at.strftime("%b %d"),
                "average_score": to_score10(session.overall_score),
                "mode": session.mode,
                "difficulty": session.difficulty,
            }
            for session in sessions
            if session.completed_at and session.overall_score is not None
        ],
    })
