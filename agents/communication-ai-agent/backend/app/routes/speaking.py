import json
import time
from datetime import datetime

import httpx
from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError

from ..extensions import db, limiter
from ..models import GeneratedTopic, SpeakingSession, SpeakingTurn, Topic, User
from ..services import groq_service
from ..services.daily_challenges import SPEAKING_DAILY, activity_status, backfill_today_from_completed_sessions, complete_daily_activity, mark_activity_started, today_challenge_date
from ..utils.score_utils import convert_scores_dict, to_score10

speaking_bp = Blueprint("speaking", __name__)

ALLOWED_DIFFICULTIES = {"easy", "medium", "hard"}
ALLOWED_MODES = {"topic", "daily"}
ALLOWED_TOTAL_TURNS = {5, 10, 15, 20, 25, 30}
DAILY_TOTAL_QUESTIONS = 20
DAILY_CATEGORIES = {
    "General Daily Talk",
    "Morning Routine",
    "Workplace",
    "College",
    "Shopping",
    "Travel",
    "Restaurant",
    "Phone Conversation",
    "Meeting a Friend",
    "Weekend Plans",
}
DEFAULT_SPEAKING_TOPICS = {
    "easy": {
        "My Family": "Talk about your family members and home life",
        "My Daily Routine": "Describe what you do on a normal day",
        "My Favourite Food": "Talk about food you like and why",
        "My Hobby": "Describe a hobby you enjoy",
        "My Hometown": "Talk about your city, town, or village",
        "My Best Friend": "Describe your friend and your friendship",
    },
    "medium": {
        "My Career Goal": "Explain your future career plans",
        "My College Experience": "Discuss learning, friends, and campus life",
        "My Current Project": "Explain a project you are working on",
        "Importance of Communication": "Discuss why communication skills matter",
        "Time Management": "Talk about planning and using time well",
        "Learning New Skills": "Discuss how people learn and improve",
    },
    "hard": {
        "Impact of Artificial Intelligence": "Analyze how AI affects work and society",
        "Remote Work Versus Office Work": "Compare remote and office work communication",
        "Leadership and Communication": "Discuss communication in leadership",
        "Ethical Challenges in Technology": "Explore technology ethics and responsibility",
        "Future of Education": "Discuss how education may change",
        "Workplace Conflict Resolution": "Discuss handling disagreement professionally",
    },
}
GENERATED_TOPIC_CACHE_TTL_SECONDS = 45 * 60
GENERATED_TOPIC_REFRESH_SECONDS = 30
_generated_topic_cache = {}
_generated_topic_refresh_log = {}


def _avg(*values):
    values = [v for v in values if v is not None]
    return round(sum(values) / len(values), 1) if values else None


def _api_error(message, error_code, status=400):
    return jsonify({"success": False, "message": message, "error_code": error_code}), status


def _custom_topic_error(message="Enter a valid topic title and description."):
    return jsonify({
        "success": False,
        "code": "INVALID_CUSTOM_TOPIC",
        "error_code": "INVALID_CUSTOM_TOPIC",
        "message": message,
    }), 400


def _validate_custom_topic_payload(data, mode, difficulty):
    if mode != "topic":
        return None, None, _custom_topic_error("Custom topics are only available in Topic-wise mode.")
    if difficulty not in ALLOWED_DIFFICULTIES:
        return None, None, _custom_topic_error()

    title_value = data.get("topic_title")
    description_value = data.get("topic_description")
    if not isinstance(title_value, str) or not isinstance(description_value, str):
        return None, None, _custom_topic_error()

    title = title_value.strip()
    description = description_value.strip()
    if len(title) < 3 or len(title) > 80:
        return None, None, _custom_topic_error("Topic title must be 3 to 80 characters.")
    if len(description) < 10 or len(description) > 500:
        return None, None, _custom_topic_error("Topic description must be 10 to 500 characters.")
    return title, description, None


def _ensure_speaking_schema():
    inspector = inspect(db.engine)
    session_columns = {column["name"] for column in inspector.get_columns("speaking_sessions")}
    turn_columns = {column["name"] for column in inspector.get_columns("speaking_turns")}

    session_alters = {
        "generated_topic_id": "ADD COLUMN generated_topic_id VARCHAR(64) NULL AFTER mode",
        "topic_description": "ADD COLUMN topic_description VARCHAR(500) NULL AFTER topic_title",
        "daily_category": "ADD COLUMN daily_category VARCHAR(120) NULL AFTER topic_title",
        "answered_turns": "ADD COLUMN answered_turns INT DEFAULT 0 AFTER total_turns",
        "ended_by_user": "ADD COLUMN ended_by_user BOOLEAN NOT NULL DEFAULT FALSE AFTER answered_turns",
        "strengths_json": "ADD COLUMN strengths_json TEXT NULL AFTER summary_feedback",
        "weaknesses_json": "ADD COLUMN weaknesses_json TEXT NULL AFTER strengths_json",
        "common_mistakes_json": "ADD COLUMN common_mistakes_json TEXT NULL AFTER weaknesses_json",
        "recommendation": "ADD COLUMN recommendation TEXT NULL AFTER common_mistakes_json",
        "next_practice_suggestion": "ADD COLUMN next_practice_suggestion TEXT NULL AFTER recommendation",
        "session_date": "ADD COLUMN session_date DATE NULL",
        "total_questions": "ADD COLUMN total_questions INT NULL",
        "current_question": "ADD COLUMN current_question INT NULL",
        "daily_questions_json": "ADD COLUMN daily_questions_json TEXT NULL",
        "daily_vocabulary_json": "ADD COLUMN daily_vocabulary_json TEXT NULL",
        "daily_vocab_used_json": "ADD COLUMN daily_vocab_used_json TEXT NULL",
        "clarity_score": "ADD COLUMN clarity_score FLOAT NULL",
    }
    turn_alters = {
        "answer_time_seconds": "ADD COLUMN answer_time_seconds INT NULL AFTER user_answer",
        "submission_id": "ADD COLUMN submission_id VARCHAR(160) NULL AFTER answer_time_seconds",
        "submission_response_json": "ADD COLUMN submission_response_json LONGTEXT NULL AFTER submission_id",
        "corrected_answer": "ADD COLUMN corrected_answer TEXT NULL AFTER user_answer",
        "better_natural_answer": "ADD COLUMN better_natural_answer TEXT NULL AFTER corrected_answer",
        "feedback_json": "ADD COLUMN feedback_json TEXT NULL AFTER better_natural_answer",
        "overall_score": "ADD COLUMN overall_score FLOAT NULL AFTER knowledge_score",
        "reaction": "ADD COLUMN reaction TEXT NULL",
        "natural_version": "ADD COLUMN natural_version TEXT NULL",
        "explanation": "ADD COLUMN explanation TEXT NULL",
        "clarity_score": "ADD COLUMN clarity_score FLOAT NULL",
    }

    for column, ddl in session_alters.items():
        if column not in session_columns:
            db.session.execute(text(f"ALTER TABLE speaking_sessions {ddl}"))
    for column, ddl in turn_alters.items():
        if column not in turn_columns:
            db.session.execute(text(f"ALTER TABLE speaking_turns {ddl}"))
    # Existing installations need the same idempotency guarantee as fresh schemas.
    indexes = {index["name"] for index in inspect(db.engine).get_indexes("speaking_turns")}
    indexes.update(constraint["name"] for constraint in inspect(db.engine).get_unique_constraints("speaking_turns") if constraint.get("name"))
    if "uq_speaking_turn_submission" not in indexes:
        db.session.execute(text(
            "CREATE UNIQUE INDEX uq_speaking_turn_submission "
            "ON speaking_turns (session_id, submission_id)"
        ))
    db.session.commit()


def _answered_turns(session):
    return [turn for turn in session.turns if turn.user_answer]


def _history(session):
    return [
        {"question": turn.ai_question, "answer": turn.user_answer}
        for turn in session.turns
        if turn.user_answer
    ]


def _feedback_response(feedback):
    if not isinstance(feedback, dict):
        return feedback
    return {**feedback, "scores": convert_scores_dict(feedback.get("scores"))}


def _apply_feedback_to_turn(turn, feedback):
    scores = feedback.get("scores") if isinstance(feedback.get("scores"), dict) else {}
    turn.corrected_answer = feedback.get("corrected_answer")
    turn.better_natural_answer = feedback.get("better_natural_answer")
    turn.reaction = feedback.get("reaction")
    turn.natural_version = feedback.get("natural_version") or feedback.get("better_natural_answer")
    turn.explanation = feedback.get("short_explanation") or feedback.get("explanation")
    turn.feedback_json = json.dumps(feedback)
    turn.feedback = feedback.get("short_feedback")
    turn.confidence_score = scores.get("confidence")
    turn.fluency_score = scores.get("fluency")
    turn.grammar_score = scores.get("grammar")
    turn.clarity_score = scores.get("clarity")
    turn.knowledge_score = scores.get("knowledge")
    turn.overall_score = scores.get("overall")


def _json_list(value):
    if not value:
        return []
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, list) else []
    except (TypeError, json.JSONDecodeError):
        return []


def _turn_payload(turn):
    feedback = None
    if turn.feedback_json:
        try:
            feedback = json.loads(turn.feedback_json)
            feedback = _feedback_response(feedback)
        except json.JSONDecodeError:
            feedback = None
    return {
        "turn_number": turn.turn_number,
        "turn_id": turn.id,
        "ai_question": turn.ai_question,
        "user_answer": turn.user_answer,
        "answer_time_seconds": turn.answer_time_seconds,
        "reaction": turn.reaction,
        "natural_version": turn.natural_version,
        "explanation": turn.explanation,
        "feedback": feedback,
        "scores": {
            "confidence": to_score10(turn.confidence_score),
            "fluency": to_score10(turn.fluency_score),
            "grammar": to_score10(turn.grammar_score),
            "clarity": to_score10(getattr(turn, "clarity_score", None)),
            "knowledge": to_score10(turn.knowledge_score),
            "overall": to_score10(turn.overall_score),
        } if turn.user_answer else None,
    }


def _session_payload(session):
    current_turn = next((turn for turn in session.turns if not turn.user_answer), None)
    return {
        "session_id": session.id,
        "mode": "daily" if session.mode in {"daily", "daily_conversation"} else session.mode,
        "difficulty": session.difficulty,
        "generated_topic_id": session.generated_topic_id,
        "topic_title": session.topic_title,
        "topic_description": session.topic_description,
        "daily_category": session.daily_category,
        "session_date": session.session_date.isoformat() if session.session_date else None,
        "total_turns": session.total_questions or session.total_turns,
        "answered_turns": session.answered_turns,
        "daily_vocabulary": _json_list(session.daily_vocabulary_json),
        "daily_vocab_used": _json_list(session.daily_vocab_used_json),
        "turn_number": current_turn.turn_number if current_turn else min(session.answered_turns + 1, session.total_turns),
        "question": current_turn.ai_question if current_turn else None,
        "turns": [_turn_payload(turn) for turn in session.turns],
        "status": session.status,
    }


def _ensure_default_topic(topic_title, difficulty):
    description = DEFAULT_SPEAKING_TOPICS.get(difficulty, {}).get(topic_title)
    if not description:
        return None

    topic = Topic.query.filter_by(category="speaking", title=topic_title).first()
    if topic:
        topic.description = description
        topic.difficulty = difficulty
        return topic

    topic = Topic(category="speaking", title=topic_title, description=description, difficulty=difficulty)
    db.session.add(topic)
    db.session.flush()
    return topic


def _ensure_default_topics_for_difficulty(difficulty):
    for title in DEFAULT_SPEAKING_TOPICS.get(difficulty, {}):
        _ensure_default_topic(title, difficulty)
    db.session.commit()


def _generated_topic_cache_key(difficulty):
    return f"speaking_topics_{difficulty}"


def _cached_generated_topics(difficulty):
    cached = _generated_topic_cache.get(_generated_topic_cache_key(difficulty))
    if not cached:
        return None
    if time.time() - cached["created_at"] > GENERATED_TOPIC_CACHE_TTL_SECONDS:
        _generated_topic_cache.pop(_generated_topic_cache_key(difficulty), None)
        return None
    return cached["payload"]


def _cache_generated_topics(difficulty, payload):
    _generated_topic_cache[_generated_topic_cache_key(difficulty)] = {
        "created_at": time.time(),
        "payload": payload,
    }


def _is_numeric_topic_id(topic_id):
    try:
        int(topic_id)
        return True
    except (TypeError, ValueError):
        return False


def _normalize_start_mode(mode):
    value = (mode or "").strip().lower()
    if value in {"topic", "topic_wise", "topic-wise"}:
        return "topic"
    if value in {"daily", "daily_conversation", "daily-conversation"}:
        return "daily"
    return value


def _summary_payload(session):
    return {
        "overall_score": to_score10(session.overall_score),
        "confidence_score": to_score10(session.confidence_score),
        "fluency_score": to_score10(session.fluency_score),
        "grammar_score": to_score10(session.grammar_score),
        "knowledge_score": None if session.mode == "daily_conversation" else to_score10(session.knowledge_score),
        "clarity_score": to_score10(getattr(session, "clarity_score", None)),
        "summary_feedback": session.summary_feedback,
        "strengths": getattr(session, "_summary_strengths", None) or _json_list(session.strengths_json),
        "areas_to_improve": getattr(session, "_summary_areas", None) or _json_list(session.weaknesses_json),
        "common_mistakes": _json_list(session.common_mistakes_json),
        "recommendation": session.recommendation,
        "next_practice_suggestion": session.next_practice_suggestion,
        "answered_turns": session.answered_turns,
        "total_turns": session.total_turns,
        "ended_by_user": session.ended_by_user,
    }


def _finalize_session(session, ended_by_user=False):
    answered = _answered_turns(session)
    session.answered_turns = len(answered)
    session.confidence_score = _avg(*[t.confidence_score for t in answered])
    session.fluency_score = _avg(*[t.fluency_score for t in answered])
    session.grammar_score = _avg(*[t.grammar_score for t in answered])
    session.clarity_score = _avg(*[t.clarity_score for t in answered])
    session.knowledge_score = _avg(*[t.knowledge_score for t in answered]) if session.mode == "topic" else None
    score_values = [session.confidence_score, session.fluency_score, session.grammar_score]
    if session.mode == "daily_conversation":
        score_values.append(session.clarity_score)
    else:
        score_values.append(session.knowledge_score)
    session.overall_score = _avg(*score_values)
    session.ended_by_user = ended_by_user
    session.status = "completed"
    session.completed_at = datetime.utcnow()

    if answered:
        summary = groq_service.summarize_speaking_session(
            session.mode, session.topic_title or session.daily_category, [t.to_dict() for t in answered]
        )
    else:
        summary = {
            "summary_feedback": "The conversation ended before any answers were submitted.",
            "strengths": [],
            "areas_to_improve": ["Try one complete answer in the next session."],
        }
    session.summary_feedback = summary["summary_feedback"]
    session.strengths_json = json.dumps(summary.get("strengths", []))
    session.weaknesses_json = json.dumps(summary.get("areas_to_improve", []))
    session.common_mistakes_json = json.dumps(summary.get("common_mistakes", []))
    session.recommendation = summary.get("recommendation")
    session.next_practice_suggestion = summary.get("next_practice_suggestion")
    session._summary_strengths = summary["strengths"]
    session._summary_areas = summary["areas_to_improve"]
    return summary


def _daily_questions_from_session(session):
    try:
        questions = json.loads(session.daily_questions_json or "[]")
        return questions if isinstance(questions, list) and len(questions) == DAILY_TOTAL_QUESTIONS else []
    except (TypeError, json.JSONDecodeError):
        return []


def _daily_summary_extras(session):
    answered = [turn for turn in session.turns if turn.user_answer]
    best = max(answered, key=lambda turn: turn.overall_score if turn.overall_score is not None else -1, default=None)
    needs = min(answered, key=lambda turn: turn.overall_score if turn.overall_score is not None else 101, default=None)

    def compact(turn):
        if not turn:
            return None
        return {
            "question": turn.ai_question,
            "answer": turn.user_answer,
            "corrected_answer": turn.corrected_answer,
            "natural_version": turn.natural_version,
            "score": to_score10(turn.overall_score),
        }

    return {
        "best_answer": compact(best),
        "needs_practice": compact(needs),
        "daily_vocabulary": _json_list(session.daily_vocabulary_json),
        "daily_vocab_used": _json_list(session.daily_vocab_used_json),
    }


def _daily_start_payload(session, status_code=200):
    payload = _session_payload(session)
    payload.update({
        "success": True,
        "daily": True,
        "total_questions": DAILY_TOTAL_QUESTIONS,
        "question_source": "stored",
    })
    if session.status == "completed":
        payload["summary"] = {
            **_summary_payload(session),
            **_daily_summary_extras(session),
            "turns": [_turn_payload(turn) for turn in session.turns],
            "daily_vocabulary": _json_list(session.daily_vocabulary_json),
            "daily_vocab_used": _json_list(session.daily_vocab_used_json),
        }
    return jsonify(payload), status_code


def _create_or_restore_daily_session(user_id):
    today = today_challenge_date()
    session = (
        SpeakingSession.query.filter_by(
            user_id=user_id,
            mode="daily_conversation",
            session_date=today,
        )
        .filter(SpeakingSession.status.in_(["in_progress", "paused"]))
        .order_by(SpeakingSession.created_at.desc(), SpeakingSession.id.desc())
        .first()
    )
    if session:
        return session, False

    completed_session = (
        SpeakingSession.query.filter_by(
            user_id=user_id,
            mode="daily_conversation",
            session_date=today,
            status="completed",
        )
        .order_by(SpeakingSession.created_at.desc(), SpeakingSession.id.desc())
        .first()
    )
    if completed_session:
        return completed_session, False

    for active in SpeakingSession.query.filter_by(user_id=user_id, status="in_progress").all():
        if active.mode != "daily_conversation":
            _close_session_without_summary(active)

    question_source = "groq"
    try:
        questions, vocabulary = groq_service.generate_daily_conversation_set()
    except Exception as exc:
        current_app.logger.warning("Daily question set unavailable; using fallback: %s", exc)
        questions, vocabulary = groq_service.fallback_daily_conversation_set()
        question_source = "fallback"

    session = SpeakingSession(
        user_id=user_id,
        mode="daily_conversation",
        topic_title="Daily Conversation",
        topic_description="Everyday conversation practice",
        daily_category="Everyday Conversation",
        session_date=today,
        total_questions=DAILY_TOTAL_QUESTIONS,
        current_question=1,
        daily_questions_json=json.dumps(questions),
        daily_vocabulary_json=json.dumps(vocabulary),
        daily_vocab_used_json=json.dumps([]),
        difficulty="daily",
        status="in_progress",
        total_turns=DAILY_TOTAL_QUESTIONS,
        answered_turns=0,
    )
    db.session.add(session)
    db.session.flush()
    for item in questions:
        db.session.add(SpeakingTurn(session_id=session.id, turn_number=item["number"], ai_question=item["question"]))
    db.session.commit()
    session._question_source = question_source
    return session, True


def _respond_daily(session, current_turn, answer, answer_time_seconds):
    answered_before = [turn for turn in session.turns if turn.user_answer]
    next_turn = next((turn for turn in session.turns if turn.turn_number > current_turn.turn_number and not turn.user_answer), None)
    previous_turns = [
        {"turn_number": turn.turn_number, "question": turn.ai_question, "answer": turn.user_answer}
        for turn in answered_before
    ]
    vocabulary = _json_list(session.daily_vocabulary_json)
    next_question_source = "stored"
    if next_turn:
        history_for_next_question = [
            {"question": turn.ai_question, "answer": groq_service.strip_completion_command(turn.user_answer)}
            for turn in answered_before
        ]
        history_for_next_question.append({
            "question": current_turn.ai_question,
            "answer": groq_service.strip_completion_command(answer),
        })
        previous_questions = [turn.ai_question for turn in session.turns if turn.turn_number <= current_turn.turn_number]
        try:
            next_turn.ai_question = groq_service.generate_speaking_question(
                "daily",
                session.difficulty,
                session.topic_title,
                next_turn.turn_number,
                history_for_next_question[-5:],
                total_turns=session.total_turns or DAILY_TOTAL_QUESTIONS,
                daily_category=session.daily_category,
                previous_questions=previous_questions,
                topic_description=session.topic_description,
            )
            next_question_source = "groq"
        except groq_service.GroqRateLimitError as exc:
            current_app.logger.warning("Daily follow-up question rate limit exhausted; using contextual fallback: %s", exc)
            next_turn.ai_question = groq_service.fallback_speaking_question(
                "daily",
                session.difficulty,
                session.topic_title,
                next_turn.turn_number,
                history_for_next_question[-5:],
                total_turns=session.total_turns or DAILY_TOTAL_QUESTIONS,
                daily_category=session.daily_category,
                previous_questions=previous_questions,
                topic_description=session.topic_description,
            )
            next_question_source = "fallback"
        except RuntimeError as exc:
            current_app.logger.warning("Groq configuration issue during daily follow-up generation; using contextual fallback: %s", exc)
            next_turn.ai_question = groq_service.fallback_speaking_question(
                "daily",
                session.difficulty,
                session.topic_title,
                next_turn.turn_number,
                history_for_next_question[-5:],
                total_turns=session.total_turns or DAILY_TOTAL_QUESTIONS,
                daily_category=session.daily_category,
                previous_questions=previous_questions,
                topic_description=session.topic_description,
            )
            next_question_source = "fallback"
        except Exception as exc:
            current_app.logger.warning("Daily follow-up question generation failed; using contextual fallback: %s", exc, exc_info=True)
            next_turn.ai_question = groq_service.fallback_speaking_question(
                "daily",
                session.difficulty,
                session.topic_title,
                next_turn.turn_number,
                history_for_next_question[-5:],
                total_turns=session.total_turns or DAILY_TOTAL_QUESTIONS,
                daily_category=session.daily_category,
                previous_questions=previous_questions,
                topic_description=session.topic_description,
            )
            next_question_source = "fallback"
    try:
        feedback = groq_service.evaluate_daily_answer(
            current_turn.ai_question,
            answer,
            previous_turns,
            next_turn.ai_question if next_turn else None,
            vocabulary,
        )
    except Exception:
        current_app.logger.exception("Daily answer feedback unavailable")
        feedback = {
            "reaction": "Thanks for sharing that.",
            "corrected_answer": None,
            "natural_version": None,
            "short_tip": "",
            "scores": {"confidence": None, "fluency": None, "grammar": None, "clarity": None, "overall": None},
            "vocabulary_used": [],
            "source": "fallback",
        }
    current_turn.user_answer = answer
    current_turn.answer_time_seconds = answer_time_seconds or None
    _apply_feedback_to_turn(current_turn, feedback)
    session.answered_turns = len(_answered_turns(session))
    session.current_question = next_turn.turn_number if next_turn else DAILY_TOTAL_QUESTIONS
    used = set(_json_list(session.daily_vocab_used_json))
    for word in feedback.get("vocabulary_used", []):
        used.add(word)
    session.daily_vocab_used_json = json.dumps(sorted(used))

    if session.answered_turns >= DAILY_TOTAL_QUESTIONS:
        complete_daily_activity(session.user_id, SPEAKING_DAILY, session.id, result_id=current_turn.id)

    if not next_turn:
        history_for_next_question = [
            {"question": turn.ai_question, "answer": groq_service.strip_completion_command(turn.user_answer)}
            for turn in _answered_turns(session)[-5:]
        ]
        previous_questions = [turn.ai_question for turn in session.turns]
        next_turn_number = max((turn.turn_number for turn in session.turns), default=current_turn.turn_number) + 1
        try:
            next_question = groq_service.generate_speaking_question(
                "daily",
                session.difficulty,
                session.topic_title,
                next_turn_number,
                history_for_next_question,
                total_turns=session.total_turns or DAILY_TOTAL_QUESTIONS,
                daily_category=session.daily_category,
                previous_questions=previous_questions,
                topic_description=session.topic_description,
            )
            next_question_source = "groq"
        except Exception as exc:
            current_app.logger.warning("Daily open-ended follow-up generation failed; using fallback: %s", exc, exc_info=True)
            next_question = groq_service.fallback_speaking_question(
                "daily",
                session.difficulty,
                session.topic_title,
                next_turn_number,
                history_for_next_question,
                total_turns=session.total_turns or DAILY_TOTAL_QUESTIONS,
                daily_category=session.daily_category,
                previous_questions=previous_questions,
                topic_description=session.topic_description,
            )
            next_question_source = "fallback"
        next_turn = SpeakingTurn(session_id=session.id, turn_number=next_turn_number, ai_question=next_question)
        db.session.add(next_turn)

    session.status = "in_progress"
    payload = {
        "done": False,
        "session_id": session.id,
        "feedback_turn_id": current_turn.id,
        "turn_number": next_turn.turn_number,
        "total_turns": DAILY_TOTAL_QUESTIONS,
        "feedback": _feedback_response(feedback),
        "next_question": next_turn.ai_question,
        "next_question_source": next_question_source,
        "daily_vocabulary": vocabulary,
        "daily_vocab_used": sorted(used),
        "turns": [_turn_payload(turn) for turn in session.turns],
    }
    current_turn.submission_response_json = json.dumps(payload)
    db.session.commit()
    return payload


def _close_session_without_summary(session):
    session.answered_turns = len(_answered_turns(session))
    session.ended_by_user = True
    session.status = "ended_by_user"
    session.completed_at = datetime.utcnow()


def _saved_submission_response(turn):
    if not turn.submission_response_json:
        return None
    try:
        payload = json.loads(turn.submission_response_json)
    except (TypeError, json.JSONDecodeError):
        return None
    return jsonify(payload)


@speaking_bp.get("/topics")
@jwt_required()
def list_topics():
    difficulty = (request.args.get("difficulty") or "").strip().lower()
    if difficulty and difficulty not in ALLOWED_DIFFICULTIES:
        return _api_error("difficulty must be easy, medium or hard", "INVALID_DIFFICULTY")

    query = Topic.query.filter_by(category="speaking")
    if difficulty:
        query = query.filter_by(difficulty=difficulty)
    topics = query.order_by(Topic.title.asc()).all()
    if difficulty and not topics:
        try:
            _ensure_default_topics_for_difficulty(difficulty)
            topics = query.order_by(Topic.title.asc()).all()
        except SQLAlchemyError:
            current_app.logger.exception("Could not seed speaking topics")
            return _api_error("The speaking topics could not be loaded from the database.", "DATABASE_UNAVAILABLE", 503)
    return jsonify({"success": True, "topics": [t.to_dict() for t in topics]})


@speaking_bp.get("/generated-topics")
@jwt_required()
def generated_topics():
    user_id = get_jwt_identity()
    difficulty = (request.args.get("difficulty") or "medium").strip().lower()
    refresh = (request.args.get("refresh") or "").strip().lower() in {"1", "true", "yes"}
    if difficulty not in ALLOWED_DIFFICULTIES:
        return _api_error("difficulty must be easy, medium or hard", "INVALID_DIFFICULTY")

    cached = _cached_generated_topics(difficulty)
    refresh_key = f"{user_id}:{difficulty}"
    now = time.time()
    last_refresh = _generated_topic_refresh_log.get(refresh_key, 0)

    if refresh and cached and now - last_refresh < GENERATED_TOPIC_REFRESH_SECONDS:
        payload = {**cached, "rate_limited": True}
        return jsonify({"success": True, "data": payload})
    if cached and not refresh:
        return jsonify({"success": True, "data": cached})

    payload = groq_service.generate_speaking_topics(difficulty)
    if refresh:
        _generated_topic_refresh_log[refresh_key] = now
    _cache_generated_topics(difficulty, payload)
    return jsonify({"success": True, "data": payload})


@speaking_bp.get("/active")
@jwt_required()
def active_session():
    user_id = int(get_jwt_identity())
    try:
        _ensure_speaking_schema()
    except SQLAlchemyError:
        current_app.logger.exception("Speaking schema check failed")
        return _api_error("The speaking database schema is not ready.", "DATABASE_SCHEMA_OUTDATED", 503)
    session = (
        SpeakingSession.query.filter(
            SpeakingSession.user_id == user_id,
            SpeakingSession.mode.in_(["topic", "daily", "daily_conversation"]),
            SpeakingSession.status.in_(["in_progress", "paused"]),
        )
        .order_by(SpeakingSession.created_at.desc())
        .first()
    )
    return jsonify({"session": _session_payload(session) if session else None})


@speaking_bp.get("/daily")
@jwt_required()
def daily_preview():
    user_id = int(get_jwt_identity())
    try:
        # Daily preview can be the first Speaking request after a deployment.
        # Reconcile the live database before loading the relationship, because
        # SpeakingTurn now includes the idempotency columns.
        _ensure_speaking_schema()
        session, created = _create_or_restore_daily_session(user_id)
        if session.status in {"in_progress", "paused"}:
            mark_activity_started(user_id, SPEAKING_DAILY, session_id=session.id)
        payload = _session_payload(session)
        payload.update({"success": True, "daily": True, "created": created, "total_questions": DAILY_TOTAL_QUESTIONS})
        db.session.commit()
        return jsonify(payload)
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Daily preview could not be loaded")
        return _api_error("Today's conversation could not be loaded right now.", "DAILY_SESSION_UNAVAILABLE", 503)


@speaking_bp.get("/daily-challenge-status")
@jwt_required()
def daily_challenge_status():
    user_id = int(get_jwt_identity())
    try:
        backfill_today_from_completed_sessions(user_id)
        payload = activity_status(user_id, SPEAKING_DAILY)
        db.session.commit()
        return jsonify(payload)
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Speaking daily challenge status query failed")
        return _api_error("Today's speaking challenge status could not be loaded right now.", "DAILY_CHALLENGE_STATUS_UNAVAILABLE", 503)


@speaking_bp.get("/session/<int:session_id>")
@jwt_required()
def get_session(session_id):
    user_id = int(get_jwt_identity())
    try:
        _ensure_speaking_schema()
    except SQLAlchemyError:
        current_app.logger.exception("Speaking schema check failed")
        return _api_error("The speaking database schema is not ready.", "DATABASE_SCHEMA_OUTDATED", 503)
    session = SpeakingSession.query.filter_by(id=session_id, user_id=user_id).first_or_404()
    return jsonify({"session": _session_payload(session)})


@speaking_bp.post("/start")
@jwt_required()
def start_session():
    user_id = int(get_jwt_identity())
    data = request.get_json(silent=True) or {}

    mode = _normalize_start_mode(data.get("mode"))
    topic_source = (data.get("topic_source") or "").strip().lower()
    if topic_source == "custom" and mode != "topic":
        return _custom_topic_error("Custom topics are only available in Topic-wise mode.")
    if mode == "daily":
        try:
            _ensure_speaking_schema()
            session, created = _create_or_restore_daily_session(user_id)
            if session.status in {"in_progress", "paused"}:
                mark_activity_started(user_id, SPEAKING_DAILY, session_id=session.id)
            response, status_code = _daily_start_payload(session, 201 if created else 200)
            db.session.commit()
            response.headers["X-Daily-Question-Set"] = "generated" if created else "stored"
            return response, status_code
        except SQLAlchemyError:
            db.session.rollback()
            current_app.logger.exception("Daily conversation session could not be created")
            return _api_error("The daily conversation could not be loaded right now.", "DAILY_SESSION_UNAVAILABLE", 503)

    difficulty = (data.get("difficulty") or "medium").strip().lower()
    generated_topic_id = data.get("generated_topic_id")
    topic_id = data.get("topic_id") or generated_topic_id
    topic_title = (data.get("topic_title") or "").strip()
    topic_description = (data.get("topic_description") or "").strip()
    daily_category = (data.get("daily_category") or topic_title or "General Daily Talk").strip()

    total_turns = 0

    if mode not in ALLOWED_MODES:
        return _api_error("mode must be 'topic' or 'daily'", "INVALID_MODE")
    if difficulty not in ALLOWED_DIFFICULTIES:
        return _api_error("difficulty must be easy, medium or hard", "INVALID_DIFFICULTY")
    if mode == "topic":
        if topic_source == "custom":
            topic_title, topic_description, custom_error = _validate_custom_topic_payload(data, mode, difficulty)
            if custom_error:
                return custom_error
            generated_topic_id = None
            topic_id = None
            topic = None
        else:
            topic = None
            if topic_id and _is_numeric_topic_id(topic_id):
                topic = Topic.query.filter_by(id=int(topic_id), category="speaking").first()
                if topic and topic.difficulty != difficulty:
                    return _api_error("The selected topic does not match the selected difficulty.", "TOPIC_DIFFICULTY_MISMATCH")
            if not topic and topic_title:
                topic = Topic.query.filter_by(category="speaking", title=topic_title, difficulty=difficulty).first()
            if not topic and topic_title and _is_numeric_topic_id(topic_id):
                topic = _ensure_default_topic(topic_title, difficulty)
            if topic:
                topic_title = topic.title
                topic_description = topic.description or topic_description
            elif topic_title:
                if len(topic_title) > 120:
                    return _api_error("The selected speaking topic title is too long.", "INVALID_TOPIC")
                if not topic_description:
                    return _api_error("The selected generated topic needs a description.", "INVALID_TOPIC")
                if len(topic_description) > 500:
                    return _api_error("The selected speaking topic description is too long.", "INVALID_TOPIC")
            else:
                return _api_error("Choose a valid speaking topic for the selected difficulty.", "TOPIC_NOT_FOUND")
    else:
        if generated_topic_id and topic_title:
            if len(topic_title) > 120:
                return _api_error("The generated daily situation title is too long.", "INVALID_TOPIC")
            if topic_description and len(topic_description) > 500:
                return _api_error("The generated daily situation description is too long.", "INVALID_TOPIC")
            daily_category = topic_title
        elif daily_category not in DAILY_CATEGORIES:
            return _api_error("Choose a valid daily conversation category.", "INVALID_DAILY_CATEGORY")

    try:
        _ensure_speaking_schema()
    except SQLAlchemyError:
        current_app.logger.exception("Speaking schema migration failed")
        return _api_error("The speaking database schema is not ready. Run the migration or seed command.", "DATABASE_SCHEMA_OUTDATED", 503)

    for active in SpeakingSession.query.filter_by(user_id=user_id, status="in_progress").all():
        if active.mode != "daily_conversation":
            _close_session_without_summary(active)

    session = SpeakingSession(
        user_id=user_id,
        mode=mode,
        generated_topic_id=generated_topic_id,
        topic_title=topic_title if topic_title else "Daily Conversation",
        topic_description=topic_description or None,
        daily_category=None if mode == "topic" else daily_category,
        difficulty=difficulty,
        status="in_progress",
        total_turns=total_turns,
        answered_turns=0,
    )
    db.session.add(session)
    db.session.flush()

    question_source = "groq"
    try:
        question = groq_service.generate_speaking_question(
            mode,
            difficulty,
            topic_title,
            1,
            [],
            total_turns=total_turns,
            daily_category=daily_category,
            topic_description=topic_description,
        )
    except groq_service.GroqRateLimitError as exc:
        current_app.logger.warning("Groq first question rate limit exhausted; using fallback question: %s", exc)
        question = groq_service.fallback_speaking_question(
            mode,
            difficulty,
            topic_title,
            1,
            [],
            total_turns=total_turns,
            daily_category=daily_category,
            previous_questions=[],
            topic_description=topic_description,
        )
        question_source = "fallback"
    except RuntimeError as exc:
        current_app.logger.warning("Groq configuration error: %s", exc)
        db.session.rollback()
        return _api_error("AI setup issue - please contact support.", "GROQ_CONFIG_ERROR", 503)
    except Exception as exc:
        current_app.logger.warning("Groq first question generation failed; using fallback question: %s", exc, exc_info=True)
        question = groq_service.fallback_speaking_question(
            mode,
            difficulty,
            topic_title,
            1,
            [],
            total_turns=total_turns,
            daily_category=daily_category,
            previous_questions=[],
            topic_description=topic_description,
        )
        question_source = "fallback"

    turn = SpeakingTurn(session_id=session.id, turn_number=1, ai_question=question)
    db.session.add(turn)
    if generated_topic_id:
        GeneratedTopic.query.filter_by(public_id=generated_topic_id, user_id=user_id).update({"used_in_session": True})
    db.session.commit()

    return jsonify({
        "success": True,
        "session_id": session.id,
        "turn_number": 1,
        "total_turns": total_turns,
        "question": question,
        "question_source": question_source,
        "mode": mode,
        "difficulty": difficulty,
        "generated_topic_id": generated_topic_id,
        "topic_id": topic.id if mode == "topic" and topic else topic_id if mode == "topic" else None,
        "topic_title": session.topic_title,
        "topic_description": session.topic_description,
        "daily_category": session.daily_category,
        "turns": [_turn_payload(turn)],
    }), 201


@speaking_bp.post("/respond")
@limiter.limit(lambda: current_app.config["ANSWER_RATE_LIMIT"])
@jwt_required()
def respond():
    user_id = int(get_jwt_identity())
    try:
        _ensure_speaking_schema()
    except SQLAlchemyError:
        current_app.logger.exception("Speaking schema check failed")
        return _api_error("The speaking database schema is not ready.", "DATABASE_SCHEMA_OUTDATED", 503)
    data = request.get_json(silent=True) or {}

    session_id = data.get("session_id")
    submission_id = (data.get("submission_id") or "").strip()
    answer = groq_service.strip_completion_command((data.get("answer") or "").strip())
    try:
        answer_time_seconds = int(data.get("answer_time_seconds") or 0)
    except (TypeError, ValueError):
        answer_time_seconds = 0
    answer_time_seconds = max(0, min(answer_time_seconds, 600))

    if not answer:
        return _api_error("Please speak or type an answer before submitting.", "EMPTY_ANSWER")
    if len(answer) > 5000:
        return _api_error("Answer is too long. Please keep it under 5000 characters.", "ANSWER_TOO_LONG")
    if len(submission_id) > 160:
        return _api_error("A valid submission_id is required.", "INVALID_SUBMISSION_ID")

    session = SpeakingSession.query.filter_by(id=session_id, user_id=user_id).with_for_update().first_or_404()
    if submission_id:
        existing_submission = SpeakingTurn.query.filter_by(
            session_id=session.id, submission_id=submission_id
        ).first()
        if existing_submission:
            saved_response = _saved_submission_response(existing_submission)
            if saved_response is not None:
                return saved_response
            return _api_error("This submission has already been processed.", "DUPLICATE_SUBMISSION", 409)
    # Recover a stale Daily session that was ended before its first answer.
    # This can happen when an older tab/server version called /end while the
    # current tab was still recording. Do not reopen completed sessions or any
    # session that already contains an answer.
    if (
        session.mode == "daily_conversation"
        and session.status == "ended_by_user"
        and session.answered_turns == 0
        and not _answered_turns(session)
    ):
        current_app.logger.warning(
            "Reopening stale zero-answer Daily Conversation session %s for user %s",
            session.id,
            user_id,
        )
        session.status = "in_progress"
        session.ended_by_user = False
        session.completed_at = None

    if session.status != "in_progress" and not (
        session.mode == "daily_conversation" and session.status == "paused"
    ):
        return jsonify({
            "code": "SESSION_ALREADY_COMPLETED",
            "error_code": "SESSION_ALREADY_COMPLETED",
            "message": "This session has already ended.",
            "session_completed": True,
            "session_id": session.id,
            "summary_available": session.status == "completed",
        }), 409

    current_turn = next((turn for turn in session.turns if not turn.user_answer), None)
    if not current_turn:
        return _api_error("No unanswered question is available for this session.", "DUPLICATE_SUBMISSION", 409)

    submission_id = submission_id or f"legacy:{session.id}:{current_turn.turn_number}"
    existing_submission = SpeakingTurn.query.filter_by(
        session_id=session.id, submission_id=submission_id
    ).first()
    if existing_submission:
        saved_response = _saved_submission_response(existing_submission)
        if saved_response is not None:
            return saved_response
        return _api_error("This submission has already been processed.", "DUPLICATE_SUBMISSION", 409)
    current_turn.submission_id = submission_id

    if session.mode == "daily_conversation":
        return jsonify(_respond_daily(session, current_turn, answer, answer_time_seconds))

    history = _history(session)
    previous_questions = [turn.ai_question for turn in session.turns]
    should_end = False

    try:
        engine_res = groq_service.process_speaking_turn_conversation_engine(
            session.mode,
            session.difficulty,
            session.topic_title,
            current_turn.ai_question,
            answer,
            history,
            total_turns=session.total_turns,
            previous_questions=previous_questions,
            topic_description=session.topic_description,
        )
        feedback = engine_res["feedback"]
        next_question = engine_res["next_question"]
        should_end = bool(engine_res.get("should_end_session"))
        next_question_source = "groq"
        if engine_res.get("detected_new_topic"):
            session.topic_title = str(engine_res["detected_new_topic"])[:120]
    except Exception as exc:
        current_app.logger.warning("Conversation engine fallback triggered: %s", exc)
        try:
            feedback = groq_service.evaluate_speaking_answer(
                session.mode,
                session.difficulty,
                session.topic_title,
                current_turn.ai_question,
                answer,
            )
        except Exception:
            current_app.logger.exception("Groq answer evaluation failed")
            return _api_error("Could not evaluate your answer right now. Please retry.", "GROQ_UNAVAILABLE", 502)

        next_turn_number = current_turn.turn_number + 1
        try:
            next_question = groq_service.generate_speaking_question(
                session.mode,
                session.difficulty,
                session.topic_title,
                next_turn_number,
                history,
                total_turns=session.total_turns,
                daily_category=session.daily_category,
                previous_questions=previous_questions,
                topic_description=session.topic_description,
            )
            next_question_source = "groq"
        except Exception:
            next_question = groq_service.fallback_speaking_question(
                session.mode,
                session.difficulty,
                session.topic_title,
                next_turn_number,
                history,
                total_turns=session.total_turns,
                daily_category=session.daily_category,
                previous_questions=previous_questions,
                topic_description=session.topic_description,
            )
            next_question_source = "fallback"

    current_turn.user_answer = answer
    current_turn.answer_time_seconds = answer_time_seconds or None
    _apply_feedback_to_turn(current_turn, feedback)
    session.answered_turns = len(_answered_turns(session))

    if should_end or (session.total_turns and session.answered_turns >= session.total_turns):
        summary = _finalize_session(session, ended_by_user=should_end)
        db.session.commit()
        payload = {
            "done": True,
            "session_id": session.id,
            "status": session.status,
            "answered_turns": session.answered_turns,
            "total_turns": session.total_turns,
            "summary": {
                **_summary_payload(session),
                "strengths": summary.get("strengths", []),
                "areas_to_improve": summary.get("areas_to_improve", []),
                "turns": [_turn_payload(turn) for turn in session.turns],
            },
            "feedback": _feedback_response(feedback),
            "next_question": next_question,
        }
        current_turn.submission_response_json = json.dumps(payload)
        db.session.commit()
        return jsonify(payload)

    next_turn_number = current_turn.turn_number + 1
    next_turn = SpeakingTurn(session_id=session.id, turn_number=next_turn_number, ai_question=next_question)
    db.session.add(next_turn)
    payload = {
        "done": False,
        "session_id": session.id,
        "feedback_turn_id": current_turn.id,
        "turn_number": next_turn_number,
        "total_turns": session.total_turns,
        "feedback": _feedback_response(feedback),
        "next_question": next_question,
        "next_question_source": next_question_source,
        "turns": [_turn_payload(turn) for turn in session.turns],
    }
    current_turn.submission_response_json = json.dumps(payload)
    db.session.commit()

    return jsonify(payload)


@speaking_bp.post("/transcribe")
@limiter.limit("12 per minute")
@jwt_required()
def transcribe_audio():
    audio_file = request.files.get("audio")
    if not audio_file:
        return _api_error("No audio file was received.", "AUDIO_MISSING", 400)

    audio_bytes = audio_file.read()
    if not audio_bytes:
        return _api_error("The recorded audio was empty.", "AUDIO_EMPTY", 400)

    try:
        transcript = groq_service.transcribe_speaking_audio(
            audio_bytes,
            filename=audio_file.filename or "speaking-answer.webm",
            content_type=audio_file.mimetype or "audio/webm",
        )
    except ValueError as exc:
        return _api_error(str(exc), "INVALID_AUDIO", 400)
    except RuntimeError as exc:
        current_app.logger.warning("Speaking audio transcription setup error: %s", exc)
        return _api_error("AI transcription setup issue - please contact support.", "GROQ_CONFIG_ERROR", 503)
    except httpx.HTTPStatusError as exc:
        current_app.logger.warning("Speaking audio transcription HTTP error: %s", exc)
        return _api_error("Audio transcription is temporarily unavailable. Please type your answer.", "TRANSCRIPTION_UNAVAILABLE", 502)
    except Exception:
        current_app.logger.exception("Speaking audio transcription failed")
        return _api_error("Audio transcription is temporarily unavailable. Please type your answer.", "TRANSCRIPTION_UNAVAILABLE", 502)

    return jsonify({
        "success": True,
        "transcript": transcript,
        "has_transcript": bool(transcript),
    })


@speaking_bp.post("/turns/<int:turn_id>/retry-correction")
@limiter.limit("6 per minute")
@jwt_required()
def retry_turn_correction(turn_id):
    user_id = int(get_jwt_identity())
    try:
        _ensure_speaking_schema()
    except SQLAlchemyError:
        current_app.logger.exception("Speaking schema check failed")
        return _api_error("The speaking database schema is not ready.", "DATABASE_SCHEMA_OUTDATED", 503)

    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id")
    turn = (
        SpeakingTurn.query.join(SpeakingSession)
        .filter(SpeakingTurn.id == turn_id, SpeakingSession.user_id == user_id)
        .first_or_404()
    )
    session = turn.session
    if session_id and int(session_id) != session.id:
        return _api_error("Turn does not belong to this session.", "TURN_SESSION_MISMATCH", 400)
    if not turn.user_answer:
        return _api_error("This turn does not have an answer to correct.", "TURN_NOT_ANSWERED", 400)

    existing_feedback = {}
    if turn.feedback_json:
        try:
            existing_feedback = json.loads(turn.feedback_json)
        except json.JSONDecodeError:
            existing_feedback = {}
    if existing_feedback.get("correction_available") and existing_feedback.get("corrected_answer"):
        return jsonify({
            "success": True,
            "turn_id": turn.id,
            "session_id": session.id,
            "feedback": _feedback_response(existing_feedback),
            "updated": False,
            "message": "A valid correction already exists for this turn.",
        })

    now = time.time()
    last_retry_at = existing_feedback.get("last_retry_correction_at")
    if isinstance(last_retry_at, (int, float)) and now - last_retry_at < 10:
        return _api_error("Please wait a moment before retrying correction.", "RETRY_TOO_SOON", 429)
    existing_feedback["last_retry_correction_at"] = now
    turn.feedback_json = json.dumps(existing_feedback)
    db.session.flush()

    answer = groq_service.strip_completion_command(turn.user_answer)
    try:
        if session.mode == "daily_conversation":
            previous_turns = [
                {"turn_number": previous.turn_number, "question": previous.ai_question, "answer": previous.user_answer}
                for previous in session.turns
                if previous.user_answer and previous.turn_number < turn.turn_number
            ]
            next_turn = next(
                (candidate for candidate in session.turns if candidate.turn_number > turn.turn_number and not candidate.user_answer),
                None,
            )
            feedback = groq_service.evaluate_daily_answer(
                turn.ai_question,
                answer,
                previous_turns,
                next_turn.ai_question if next_turn else None,
                _json_list(session.daily_vocabulary_json),
            )
        else:
            feedback = groq_service.evaluate_speaking_answer(
                session.mode,
                session.difficulty,
                session.topic_title,
                turn.ai_question,
                answer,
            )
            if not feedback.get("correction_available") and feedback.get("fallback_reason") not in {"unclear_transcript", "unclear_tense"}:
                feedback = groq_service.repair_speaking_correction(
                    session.mode,
                    session.difficulty,
                    session.topic_title,
                    turn.ai_question,
                    answer,
                )
    except httpx.HTTPStatusError as exc:
        reason = "rate_limited" if getattr(exc.response, "status_code", None) == 429 else "http_error"
        feedback = {**existing_feedback, "correction_available": False, "fallback_reason": reason}
    except httpx.TimeoutException:
        feedback = {**existing_feedback, "correction_available": False, "fallback_reason": "timeout"}
    except Exception:
        feedback = {**existing_feedback, "correction_available": False, "fallback_reason": "invalid_response"}

    scores = feedback.get("scores") if isinstance(feedback.get("scores"), dict) else {}
    has_scored_feedback = any(value is not None for value in scores.values())
    has_correction = bool(feedback.get("corrected_answer") or feedback.get("natural_version") or feedback.get("better_natural_answer"))
    if (
        session.mode == "daily_conversation"
        and feedback.get("source") == "groq"
        and (has_correction or has_scored_feedback)
    ) or (
        session.mode != "daily_conversation"
        and feedback.get("correction_available")
        and feedback.get("corrected_answer")
    ):
        feedback["last_retry_correction_at"] = now
        _apply_feedback_to_turn(turn, feedback)
        db.session.commit()
        return jsonify({
            "success": True,
            "turn_id": turn.id,
            "session_id": session.id,
            "feedback": _feedback_response(feedback),
            "updated": True,
        })

    existing_feedback["last_retry_correction_at"] = now
    existing_feedback["fallback_reason"] = feedback.get("fallback_reason") or "retry_unavailable"
    existing_feedback["correction_available"] = False
    turn.feedback_json = json.dumps(existing_feedback)
    db.session.commit()
    return jsonify({
        "success": False,
        "turn_id": turn.id,
        "session_id": session.id,
        "feedback": _feedback_response(existing_feedback),
        "updated": False,
        "message": "Correction is still unavailable. You can continue or retry later.",
    }), 503


@speaking_bp.post("/end")
@jwt_required()
def end_session():
    user_id = int(get_jwt_identity())
    try:
        _ensure_speaking_schema()
    except SQLAlchemyError:
        current_app.logger.exception("Speaking schema check failed")
        return _api_error("The speaking database schema is not ready.", "DATABASE_SCHEMA_OUTDATED", 503)
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id")

    session = SpeakingSession.query.filter_by(id=session_id, user_id=user_id).first_or_404()
    if session.status != "in_progress":
        if session.status == "ended_by_user":
            return jsonify({
                "done": False,
                "session_id": session.id,
                "status": session.status,
                "answered_turns": session.answered_turns,
                "total_turns": session.total_turns,
            })
        return jsonify({"summary": _summary_payload(session)})

    summary = _finalize_session(session, ended_by_user=True)
    if session.mode == "daily_conversation" and session.answered_turns > 0:
        complete_daily_activity(user_id, SPEAKING_DAILY, session.id)
    db.session.commit()
    return jsonify({
        "done": True,
        "session_id": session.id,
        "status": session.status,
        "answered_turns": session.answered_turns,
        "total_turns": session.total_turns,
        "summary": {
            **_summary_payload(session),
            "strengths": summary.get("strengths", []),
            "areas_to_improve": summary.get("areas_to_improve", []),
            "turns": [_turn_payload(turn) for turn in session.turns],
        },
    })


@speaking_bp.get("/progress")
@jwt_required()
def speaking_progress():
    user_id = int(get_jwt_identity())
    sessions = (
        SpeakingSession.query.filter(
            SpeakingSession.user_id == user_id,
            SpeakingSession.status == "completed",
            SpeakingSession.overall_score.isnot(None),
            SpeakingSession.completed_at.isnot(None),
        )
        .order_by(SpeakingSession.completed_at.asc())
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
