import json
import uuid
from datetime import datetime

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError

from ..extensions import db
from ..models import PronunciationAttempt, PronunciationItem, PronunciationSession, User
from ..services import groq_service
from ..services.daily_challenges import PRONUNCIATION_DAILY, activity_status, backfill_today_from_completed_sessions, complete_daily_activity, mark_activity_started, today_challenge_date
from ..services.groq_pronunciation import DAILY_CHALLENGE_SCHEMA_VERSION, generate_phonetic_hints
from ..services.pronunciation_assessment import assess_pronunciation
from ..utils.score_utils import to_score10

pronunciation_bp = Blueprint("pronunciation", __name__)

ALLOWED_DIFFICULTIES = {"easy", "medium", "hard"}
ALLOWED_MODES = {"word", "sentence", "daily", "minimal_pairs"}
PUBLIC_MODE_NAMES = {"word": "word", "sentence": "sentence", "daily": "daily_challenge", "minimal_pairs": "minimal_pairs"}
MAX_ATTEMPTS_PER_ITEM = 3
DEFAULT_OPEN_ENDED_QUESTIONS = 0


def _api_error(message, error_code, status=400):
    return jsonify({"success": False, "message": message, "error_code": error_code}), status


def _average_score(values):
    clean_values = [value for value in values if value is not None]
    return round(sum(clean_values) / len(clean_values), 1) if clean_values else None


def _pronunciation_attempts_for_summary(session):
    return [
        attempt
        for attempt in (session.attempts or [])
        if attempt.status == "completed" and attempt.overall_score is not None
    ]


def _pronunciation_summary_items(attempts):
    items = []
    for index, attempt in enumerate(attempts, start=1):
        turn = attempt.to_session_turn_dict()
        scores = turn.get("scores") or {}
        overall = to_score10(attempt.overall_score)
        label = turn.get("reference_text") or f"Item {attempt.turn_number or index}"
        items.append({
            "id": attempt.id,
            "attempt_id": attempt.public_id,
            "turn_number": attempt.turn_number or index,
            "label": label,
            "reference_text": label,
            "recognised_text": turn.get("recognised_text"),
            "overall": overall,
            "accuracy": scores.get("word_accuracy"),
            "clarity": scores.get("clarity"),
            "fluency": scores.get("fluency"),
            "completeness": scores.get("completeness"),
            "status": "Strong" if overall is not None and overall >= 8 else "Needs polish" if overall is not None and overall >= 5.5 else "Needs practice",
        })
    return items


def _pronunciation_session_summary_payload(session, summary=None):
    attempts = _pronunciation_attempts_for_summary(session)
    turns = [attempt.to_session_turn_dict() for attempt in attempts]
    items = _pronunciation_summary_items(attempts)
    overall_scores = [item["overall"] for item in items]
    average_overall = _average_score(overall_scores)

    if session.average_score is None and average_overall is not None:
        session.average_score = average_overall

    strengths = summary.get("strengths", []) if summary else json.loads(session.strengths_json or "[]")
    areas_to_improve = summary.get("areas_to_improve", []) if summary else json.loads(session.weaknesses_json or "[]")

    return {
        "success": True,
        "done": True,
        "session_id": session.id,
        "overall_score": to_score10(session.average_score) if session.average_score is not None else average_overall,
        "average_score": to_score10(session.average_score) if session.average_score is not None else average_overall,
        "average_accuracy": _average_score([item["accuracy"] for item in items]),
        "average_clarity": _average_score([item["clarity"] for item in items]),
        "average_fluency": _average_score([item["fluency"] for item in items]),
        "average_completeness": _average_score([item["completeness"] for item in items]),
        "summary_feedback": session.summary_feedback,
        "summary": session.summary_feedback,
        "strengths": strengths,
        "areas_to_improve": areas_to_improve,
        "recommendation": summary.get("recommendation") if summary else session.recommendation,
        "next_practice_suggestion": summary.get("next_practice_suggestion") if summary else session.next_practice_suggestion,
        "turns": turns,
        "items": items,
        "mode": session.mode,
        "difficulty": session.difficulty,
        "type": "pronunciation",
        "topic_title": f"{session.mode.capitalize()} Practice",
        "created_at": session.created_at.isoformat() if session.created_at else None,
    }


def _normalize_mode(value):
    mode = (value or "word").strip().lower()
    if mode in {"word_practice", "word-practice"}:
        return "word"
    if mode in {"sentence_practice", "sentence-practice"}:
        return "sentence"
    if mode in {"daily_challenge", "daily-pronunciation-challenge", "challenge"}:
        return "daily"
    if mode in {"minimal_pairs", "minimal-pairs", "minimal_pair", "minimal-pair", "minimal_pair_practice", "minimal-pair-practice", "pairs"}:
        return "minimal_pairs"
    return mode


def _public_mode(mode):
    return PUBLIC_MODE_NAMES.get(mode, mode)


def _recent_items(user_id, practice_mode, difficulty):
    rows = (
        PronunciationItem.query.filter_by(user_id=user_id, practice_mode=practice_mode, difficulty=difficulty)
        .order_by(PronunciationItem.created_at.desc())
        .limit(8)
        .all()
    )
    return [item.text for item in rows]


def _recent_daily_titles(user_id, difficulty):
    rows = (
        PronunciationItem.query.filter_by(user_id=user_id, practice_mode="daily", difficulty=difficulty)
        .order_by(PronunciationItem.created_at.desc())
        .limit(8)
        .all()
    )
    titles = []
    for item in rows:
        try:
            metadata = json.loads(item.metadata_json or "{}")
        except (TypeError, json.JSONDecodeError):
            metadata = {}
        titles.append(metadata.get("title") or item.meaning or item.text)
    return [title for title in titles if title]


def _same_item(text, recent_items):
    normalized = (text or "").strip().lower()
    return bool(normalized) and normalized in {str(item).strip().lower() for item in recent_items or []}


def _item_has_completed_attempt(user_id, item_id):
    return (
        PronunciationAttempt.query.filter_by(
            user_id=user_id,
            item_id=item_id,
            status="completed",
        ).first()
        is not None
    )


def _generated_response(item):
    data = item.to_dict()
    content = data["content"]
    if data["practice_mode"] == "daily":
        content = {
            **content,
            "challenge_id": item.id,
            "challenge_date": data["daily_date"],
            "difficulty": data["difficulty"],
            "practice_mode": "daily_challenge",
            "source": data["source"],
            "status": "not_started",
        }
    return {
        "success": True,
        "data": {
            "item_id": data["item_id"],
            "challenge_id": item.id if data["practice_mode"] == "daily" else None,
            "practice_mode": _public_mode(data["practice_mode"]),
            "difficulty": data["difficulty"],
            "challenge_date": data["daily_date"],
            "source": data["source"],
            "content": content,
            **data,
            "practice_mode": _public_mode(data["practice_mode"]),
            "content": content,
        },
    }


def _create_item(user_id, practice_mode, difficulty, daily_date=None):
    recent = _recent_daily_titles(user_id, difficulty) if practice_mode == "daily" else _recent_items(user_id, practice_mode, difficulty)
    payload = groq_service.generate_pronunciation_item(practice_mode, difficulty, recent)
    payload_title = (payload.get("metadata") or {}).get("title") or payload.get("meaning") or payload.get("text")
    if _same_item(payload_title if practice_mode == "daily" else payload.get("text"), recent):
        payload = groq_service.generate_pronunciation_item(practice_mode, difficulty, recent)
    item = PronunciationItem(
        public_id=str(uuid.uuid4()),
        user_id=user_id,
        practice_mode=practice_mode,
        item_type=payload["item_type"],
        text=payload["text"],
        meaning=payload.get("meaning"),
        example_sentence=payload.get("example_sentence"),
        syllables=payload.get("syllables"),
        difficulty=difficulty,
        expected_duration_seconds=payload.get("expected_duration_seconds"),
        source=payload.get("source", "groq"),
        metadata_json=json.dumps(payload.get("metadata", {})),
        daily_date=daily_date,
    )
    db.session.add(item)
    db.session.commit()
    return item


def _item_for_user(user_id, public_id):
    return PronunciationItem.query.filter_by(public_id=public_id, user_id=user_id).first()


def _ensure_daily_metadata(item):
    if not item or item.practice_mode != "daily":
        return item
    try:
        metadata = json.loads(item.metadata_json or "{}")
    except (TypeError, json.JSONDecodeError):
        metadata = {}
    if metadata.get("schema_version") == DAILY_CHALLENGE_SCHEMA_VERSION and isinstance(metadata.get("practice_lines"), list):
        return item
    title = item.meaning or "Daily Challenge"
    lines = [line.strip() for line in (item.text or "").splitlines() if line.strip()]
    if len(lines) < 2:
        replacement = groq_service.generate_pronunciation_item("daily", item.difficulty, _recent_daily_titles(item.user_id, item.difficulty))
        item.text = replacement["text"]
        item.meaning = replacement.get("meaning")
        item.example_sentence = replacement.get("example_sentence")
        item.expected_duration_seconds = replacement.get("expected_duration_seconds")
        item.source = replacement.get("source", item.source)
        item.syllables = replacement.get("syllables")
        item.metadata_json = json.dumps(replacement.get("metadata", {}))
        db.session.commit()
        return item
    metadata = {
        "schema_version": DAILY_CHALLENGE_SCHEMA_VERSION,
        "title": title,
        "description": "Practise today's pronunciation challenge clearly.",
        "practice_lines": lines,
        "main_sentence": "\n".join(lines),
        "challenge_phrase": lines[0],
        "focus_tip": "Practise the warm-up word first, then repeat the full sentence clearly.",
        "instructions": ["Listen once.", "Repeat each line clearly.", "Review your transcript before submitting."],
        "goal": "Complete all lines clearly.",
    }
    item.metadata_json = json.dumps(metadata)
    item.meaning = title
    item.example_sentence = lines[0]
    item.syllables = None
    db.session.commit()
    return item


def _ensure_pronunciation_schema():
    """Defensive runtime migration — adds new columns to existing tables without Alembic."""
    inspector = inspect(db.engine)

    # Add pronunciation_sessions table if not present
    existing_tables = inspector.get_table_names()
    if "pronunciation_sessions" not in existing_tables:
        db.session.execute(text(
            "CREATE TABLE pronunciation_sessions ("
            "  id INTEGER NOT NULL PRIMARY KEY AUTO_INCREMENT,"
            "  user_id INTEGER NOT NULL,"
            "  mode VARCHAR(20) NOT NULL,"
            "  difficulty VARCHAR(20) NOT NULL DEFAULT 'medium',"
            "  total_questions INTEGER NOT NULL DEFAULT 5,"
            "  questions_completed INTEGER NOT NULL DEFAULT 0,"
            "  status VARCHAR(20) NOT NULL DEFAULT 'in_progress',"
            "  average_score FLOAT NULL,"
            "  summary_feedback TEXT NULL,"
            "  strengths_json TEXT NULL,"
            "  weaknesses_json TEXT NULL,"
            "  recommendation TEXT NULL,"
            "  next_practice_suggestion TEXT NULL,"
            "  created_at DATETIME NULL,"
            "  completed_at DATETIME NULL,"
            "  CONSTRAINT fk_ps_user FOREIGN KEY (user_id) REFERENCES users (id)"
            ")"
        ))
        db.session.commit()

    # Add session_id, turn_number, sound_tags_json, and effective_difficulty to pronunciation_attempts if not present
    attempt_columns = {col["name"] for col in inspector.get_columns("pronunciation_attempts")}
    attempt_alters = {
        "session_id": "ADD COLUMN session_id INTEGER NULL AFTER item_id",
        "turn_number": "ADD COLUMN turn_number INTEGER NULL AFTER session_id",
        "sound_tags_json": "ADD COLUMN sound_tags_json TEXT NULL AFTER status",
        "effective_difficulty": "ADD COLUMN effective_difficulty VARCHAR(20) NULL AFTER sound_tags_json",
    }
    for column, ddl in attempt_alters.items():
        if column not in attempt_columns:
            db.session.execute(text(f"ALTER TABLE pronunciation_attempts {ddl}"))
            
    # Add streak_count and last_completed_date to users if not present
    user_columns = {col["name"] for col in inspector.get_columns("users")}
    user_alters = {
        "streak_count": "ADD COLUMN streak_count INTEGER NOT NULL DEFAULT 0",
        "last_completed_date": "ADD COLUMN last_completed_date DATE NULL",
    }
    for column, ddl in user_alters.items():
        if column not in user_columns:
            db.session.execute(text(f"ALTER TABLE users {ddl}"))

    db.session.commit()


def _item_to_session_payload(item):
    """Serialize a PronunciationItem into the shape expected by the frontend session flow."""
    data = item.to_dict()
    content = data["content"]
    if data["practice_mode"] == "daily":
        content = {
            **content,
            "challenge_id": item.id,
            "challenge_date": data["daily_date"],
            "difficulty": data["difficulty"],
            "practice_mode": "daily_challenge",
            "source": data["source"],
            "status": "not_started",
        }
    return {
        "item_id": data["item_id"],
        "practice_mode": _public_mode(data["practice_mode"]),
        "difficulty": data["difficulty"],
        "source": data["source"],
        "content": content,
        **data,
        "practice_mode": _public_mode(data["practice_mode"]),
        "content": content,
    }


def _normalize_minimal_pair_response(item, data):
    try:
        metadata = json.loads(item.metadata_json) if item.metadata_json else {}
    except (TypeError, json.JSONDecodeError):
        metadata = {}
    pair = metadata.get("pair") if isinstance(metadata.get("pair"), list) else []
    word_a = metadata.get("word_a") or (pair[0] if len(pair) > 0 else None)
    word_b = metadata.get("word_b") or (pair[1] if len(pair) > 1 else None)
    responses = data.get("minimal_pair_responses")
    if not isinstance(responses, list):
        responses = data.get("pair_responses")
    if not isinstance(responses, list):
        responses = []
    normalized = []
    for index, word in enumerate([word_a, word_b]):
        response = responses[index] if index < len(responses) and isinstance(responses[index], dict) else {}
        transcript = str(response.get("recognised_text") or response.get("transcript") or "").strip()
        if word:
            normalized.append({
                "word": str(word).strip(),
                "recognised_text": transcript,
                "recognition_confidence": response.get("recognition_confidence"),
                "duration_seconds": response.get("duration_seconds"),
            })
    return metadata, normalized


def _score_minimal_pair_item(item, data):
    metadata, responses = _normalize_minimal_pair_response(item, data)
    if len(responses) != 2:
        raise ValueError("Minimal pairs require two words.")
    if any(not response["recognised_text"] for response in responses):
        raise ValueError("Please record both minimal-pair words before submitting.")

    pair_results = []
    overall_scores = []
    recognised_words = []
    combined_word_results = []
    sound_tags = set()
    for response in responses:
        comparison = assess_pronunciation(
            response["word"],
            response["recognised_text"],
            response.get("recognition_confidence"),
            response.get("duration_seconds"),
            mode="word",
        )
        scores = comparison["scores"]
        overall_scores.append(scores["overall"])
        recognised_words.append((comparison.get("recognised_text") or "").strip().lower())
        combined_word_results.extend(comparison.get("word_results", []))
        for tag in comparison.get("sound_tags", []):
            sound_tags.add(tag)
        pair_results.append({
            "word": response["word"],
            "recognised_text": response["recognised_text"],
            "match_percentage": comparison["match_percentage"],
            "scores": scores,
            "word_results": comparison.get("word_results", []),
            "validation_message": comparison.get("validation_message"),
        })

    average_overall = round(sum(overall_scores) / len(overall_scores), 1)
    both_recognised_same = len(set(word for word in recognised_words if word)) == 1
    both_expected_different = responses[0]["word"].lower() != responses[1]["word"].lower()
    distinguishable = not (both_expected_different and both_recognised_same)
    if not distinguishable:
        average_overall = min(average_overall, 6.0)
    match_percentage = int(round(average_overall * 10))
    contrast = metadata.get("sound_contrast") or "target sound contrast"
    return {
        "assessment_type": "minimal_pairs_sequential_production",
        "exact_match": all(result["word"].lower() == result["recognised_text"].strip().lower() for result in pair_results),
        "validation_message": (
            "Your two words sounded distinguishable."
            if distinguishable
            else f"Your two words sounded too similar. Emphasise the {contrast} contrast."
        ),
        "match_percentage": match_percentage,
        "scores": {
            "word_accuracy": average_overall,
            "completeness": average_overall,
            "clarity": average_overall,
            "fluency": average_overall,
            "overall": average_overall,
        },
        "expected_text": item.text,
        "recognised_text": " / ".join(response["recognised_text"] for response in responses),
        "correct_words": [result["word"] for result in pair_results if result["word"].lower() == result["recognised_text"].strip().lower()],
        "missing_words": [],
        "different_words": [
            {"expected": result["word"], "recognised": result["recognised_text"]}
            for result in pair_results
            if result["word"].lower() != result["recognised_text"].strip().lower()
        ],
        "extra_words": [],
        "words_needing_practice": [
            result["word"]
            for result in pair_results
            if result["word"].lower() != result["recognised_text"].strip().lower()
        ],
        "word_results": combined_word_results,
        "minimal_pair_results": pair_results,
        "distinguishability": {
            "passed": distinguishable,
            "message": (
                "The pair sounded different enough."
                if distinguishable
                else f"The pair sounded too similar. Practise the {contrast} contrast."
            ),
            "sound_contrast": contrast,
        },
        "sound_tags": sorted(sound_tags | {contrast}),
    }


# ─── Backward-compatible existing endpoints ───────────────────────────────────

@pronunciation_bp.post("/generate")
@jwt_required()
def generate_item():
    user_id = int(get_jwt_identity())
    data = request.get_json(silent=True) or {}
    mode = _normalize_mode(data.get("practice_mode"))
    difficulty = (data.get("difficulty") or "medium").strip().lower()

    if mode not in ALLOWED_MODES:
        return _api_error("practice_mode must be word, sentence, daily_challenge or minimal_pairs", "INVALID_MODE")
    if difficulty not in ALLOWED_DIFFICULTIES:
        return _api_error("difficulty must be easy, medium or hard", "INVALID_DIFFICULTY")

    if mode == "daily":
        today = today_challenge_date()
        item = PronunciationItem.query.filter_by(
            user_id=user_id,
            practice_mode="daily",
            difficulty=difficulty,
            daily_date=today,
        ).first()
        if item:
            return jsonify(_generated_response(_ensure_daily_metadata(item)))
        daily_date = today
    else:
        daily_date = None

    try:
        item = _create_item(user_id, mode, difficulty, daily_date=daily_date)
    except SQLAlchemyError:
        current_app.logger.exception("Could not create pronunciation item")
        db.session.rollback()
        return _api_error("Pronunciation content could not be generated.", "GENERATION_FAILED", 503)

    if not item.text or item.practice_mode != mode or item.difficulty != difficulty:
        return _api_error("Pronunciation content could not be generated.", "GENERATION_FAILED", 502)
    return jsonify(_generated_response(item)), 201


@pronunciation_bp.get("/item")
@jwt_required()
def get_item():
    user_id = int(get_jwt_identity())
    mode = _normalize_mode(request.args.get("mode"))
    difficulty = (request.args.get("difficulty") or "medium").strip().lower()
    refresh = (request.args.get("refresh") or "").strip().lower() in {"1", "true", "yes"}

    if mode not in ALLOWED_MODES:
        return _api_error("mode must be word, sentence, daily or minimal_pairs", "INVALID_MODE")
    if difficulty not in ALLOWED_DIFFICULTIES:
        return _api_error("difficulty must be easy, medium or hard", "INVALID_DIFFICULTY")
    if mode == "daily":
        return daily_challenge()

    if not refresh:
        existing = (
            PronunciationItem.query.filter_by(user_id=user_id, practice_mode=mode, difficulty=difficulty)
            .order_by(PronunciationItem.created_at.desc())
            .first()
        )
        if existing:
            return jsonify({"success": True, "data": existing.to_dict()})

    try:
        item = _create_item(user_id, mode, difficulty)
    except SQLAlchemyError:
        current_app.logger.exception("Could not create pronunciation item")
        db.session.rollback()
        return _api_error("Could not save the pronunciation item.", "DATABASE_UNAVAILABLE", 503)
    return jsonify({"success": True, "data": item.to_dict()})


@pronunciation_bp.get("/daily-challenge")
@jwt_required()
def daily_challenge():
    user_id = int(get_jwt_identity())
    difficulty = (request.args.get("difficulty") or "easy").strip().lower()
    if difficulty not in ALLOWED_DIFFICULTIES:
        return _api_error("difficulty must be easy, medium or hard", "INVALID_DIFFICULTY")
    today = today_challenge_date()
    item = PronunciationItem.query.filter_by(
        user_id=user_id,
        practice_mode="daily",
        difficulty=difficulty,
        daily_date=today,
    ).first()
    if not item:
        try:
            item = _create_item(user_id, "daily", difficulty, daily_date=today)
        except SQLAlchemyError:
            current_app.logger.exception("Could not create daily pronunciation challenge")
            db.session.rollback()
            return _api_error("Could not save today's pronunciation challenge.", "DATABASE_UNAVAILABLE", 503)
    else:
        item = _ensure_daily_metadata(item)
    return jsonify(_generated_response(item))


@pronunciation_bp.get("/daily-challenge-status")
@jwt_required()
def daily_challenge_status():
    user_id = int(get_jwt_identity())
    try:
        backfill_today_from_completed_sessions(user_id)
        payload = activity_status(user_id, PRONUNCIATION_DAILY)
        db.session.commit()
        return jsonify(payload)
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Pronunciation daily challenge status query failed")
        return _api_error("Today's pronunciation challenge status could not be loaded right now.", "DAILY_CHALLENGE_STATUS_UNAVAILABLE", 503)


@pronunciation_bp.post("/start")
@jwt_required()
def start_attempt():
    user_id = int(get_jwt_identity())
    data = request.get_json(silent=True) or {}
    item = _item_for_user(user_id, data.get("item_id"))
    if not item:
        return _api_error("Pronunciation item not found.", "ITEM_NOT_FOUND", 404)

    completed_count = PronunciationAttempt.query.filter_by(user_id=user_id, item_id=item.id, status="completed").count()
    if completed_count >= MAX_ATTEMPTS_PER_ITEM:
        return _api_error("You have reached the retry limit for this item.", "RETRY_LIMIT_REACHED", 409)

    attempt = PronunciationAttempt(
        public_id=str(uuid.uuid4()),
        user_id=user_id,
        item_id=item.id,
        attempt_number=completed_count + 1,
        status="started",
    )
    db.session.add(attempt)
    db.session.commit()
    return jsonify({
        "success": True,
        "data": {
            "attempt_id": attempt.public_id,
            "attempt_number": attempt.attempt_number,
            "max_attempts": MAX_ATTEMPTS_PER_ITEM,
        },
    }), 201


# ─── New session endpoints ─────────────────────────────────────────────────────

@pronunciation_bp.post("/session/start")
@jwt_required()
def session_start():
    """Create a new PronunciationSession and generate the first item."""
    user_id = int(get_jwt_identity())
    data = request.get_json(silent=True) or {}

    mode = _normalize_mode(data.get("practice_mode"))
    difficulty = (data.get("difficulty") or "medium").strip().lower()

    if mode not in ALLOWED_MODES:
        return _api_error("practice_mode must be word, sentence, daily_challenge or minimal_pairs", "INVALID_MODE")
    if difficulty not in ALLOWED_DIFFICULTIES:
        return _api_error("difficulty must be easy, medium or hard", "INVALID_DIFFICULTY")

    total_questions = 1 if mode == "daily" else DEFAULT_OPEN_ENDED_QUESTIONS

    try:
        _ensure_pronunciation_schema()
    except SQLAlchemyError:
        db.session.rollback()
        return _api_error("The pronunciation database schema is not ready.", "DATABASE_SCHEMA_OUTDATED", 503)

    # For daily mode, reuse today's item only while it is still unfinished.
    # After the learner completes today's required daily challenge, allow
    # additional Daily Pronunciation Challenge starts to receive fresh content
    # while the dashboard's once-per-day completion status remains intact.
    if mode == "daily":
        today = today_challenge_date()
        today_item = PronunciationItem.query.filter_by(
            user_id=user_id,
            practice_mode="daily",
            difficulty=difficulty,
            daily_date=today,
        ).first()
        if today_item and not _item_has_completed_attempt(user_id, today_item.id):
            first_item = _ensure_daily_metadata(today_item)
        else:
            try:
                first_item = _create_item(
                    user_id,
                    "daily",
                    difficulty,
                    daily_date=None if today_item else today,
                )
            except SQLAlchemyError:
                current_app.logger.exception("Could not create daily pronunciation item for session")
                db.session.rollback()
                return _api_error("Could not generate pronunciation content.", "GENERATION_FAILED", 503)
    else:
        try:
            first_item = _create_item(user_id, mode, difficulty)
        except SQLAlchemyError:
            current_app.logger.exception("Could not create pronunciation item for session")
            db.session.rollback()
            return _api_error("Could not generate pronunciation content.", "GENERATION_FAILED", 503)

    session = PronunciationSession(
        user_id=user_id,
        mode=mode,
        difficulty=difficulty,
        total_questions=total_questions,
        questions_completed=0,
        status="in_progress",
    )
    db.session.add(session)
    db.session.flush()
    if mode == "daily":
        mark_activity_started(user_id, PRONUNCIATION_DAILY, session_id=session.id)
    db.session.commit()

    return jsonify({
        "success": True,
        "session_id": session.id,
        "question_number": 1,
        "total_questions": total_questions,
        "mode": mode,
        "difficulty": difficulty,
        "item": _item_to_session_payload(first_item),
    }), 201


@pronunciation_bp.get("/session/<int:session_id>")
@jwt_required()
def get_session(session_id):
    """Fetch current session progress (for page-refresh resilience)."""
    user_id = int(get_jwt_identity())
    try:
        _ensure_pronunciation_schema()
    except SQLAlchemyError:
        db.session.rollback()
        return _api_error("The pronunciation database schema is not ready.", "DATABASE_SCHEMA_OUTDATED", 503)
    session = PronunciationSession.query.filter_by(id=session_id, user_id=user_id).first()
    if not session:
        return _api_error("Pronunciation session not found.", "SESSION_NOT_FOUND", 404)
    return jsonify({"success": True, "session": session.to_detail_dict()})


# ─── Updated submit endpoint ───────────────────────────────────────────────────

@pronunciation_bp.post("/submit")
@jwt_required()
def submit_attempt():
    user_id = int(get_jwt_identity())
    data = request.get_json(silent=True) or {}
    item_id = data.get("item_id")
    attempt_id = data.get("attempt_id")
    session_id = data.get("session_id")  # optional — present in new session flow
    recognised_text = (data.get("recognised_text") or "").strip()
    has_pair_responses = isinstance(data.get("minimal_pair_responses") or data.get("pair_responses"), list)
    if not recognised_text and not has_pair_responses:
        return _api_error("Please review or type your recognised speech before submitting.", "EMPTY_TRANSCRIPT")
    if len(recognised_text) > 2000:
        return _api_error("Transcript is too long. Please keep it under 2000 characters.", "TRANSCRIPT_TOO_LONG")

    item = _item_for_user(user_id, item_id)
    if not item:
        return _api_error("Pronunciation item not found.", "ITEM_NOT_FOUND", 404)
    attempt = PronunciationAttempt.query.filter_by(public_id=attempt_id, user_id=user_id, item_id=item.id).first()
    if not attempt:
        return _api_error("Pronunciation attempt not found.", "ATTEMPT_NOT_FOUND", 404)
    if attempt.status == "completed":
        return _api_error("This pronunciation attempt was already submitted.", "DUPLICATE_SUBMISSION", 409)

    confidence = data.get("recognition_confidence")
    duration = data.get("duration_seconds")
    
    try:
        metadata = json.loads(item.metadata_json) if item.metadata_json else {}
    except (TypeError, json.JSONDecodeError):
        metadata = {}

    try:
        if item.practice_mode == "minimal_pairs":
            comparison = _score_minimal_pair_item(item, data)
            recognised_text = comparison["recognised_text"]
        else:
            comparison = assess_pronunciation(item.text, recognised_text, confidence, duration, mode=item.practice_mode)
        
        # Priority 3: Phonetic hints
        if comparison.get("words_needing_practice"):
            phonetic_hints = generate_phonetic_hints(comparison["words_needing_practice"])
        else:
            phonetic_hints = []

        feedback = groq_service.generate_pronunciation_feedback(item.text, recognised_text, comparison, item.difficulty)
        feedback["phonetic_feedback"] = phonetic_hints
        
        scores = comparison["scores"]

        attempt.status = "completed"
        attempt.recognised_text = recognised_text
        attempt.recognition_confidence = confidence
        attempt.reference_locale = (data.get("reference_locale") or "en-US")[:20]
        attempt.duration_seconds = duration
        attempt.assessment_type = comparison["assessment_type"]
        attempt.match_percentage = comparison["match_percentage"]
        attempt.word_accuracy_score = scores["word_accuracy"]
        attempt.completeness_score = scores["completeness"]
        attempt.clarity_score = scores["clarity"]
        attempt.fluency_score = scores["fluency"]
        attempt.overall_score = scores["overall"]
        attempt.comparison_json = json.dumps(comparison)
        attempt.feedback_json = json.dumps(feedback)
        attempt.sound_tags_json = json.dumps(comparison.get("sound_tags", []))
        attempt.completed_at = datetime.utcnow()
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Pronunciation submit failed: DB error")
        return _api_error("Could not save your pronunciation result. Please try again.", "SUBMIT_DB_ERROR", 500)
    except ValueError as exc:
        db.session.rollback()
        return _api_error(str(exc), "MINIMAL_PAIR_INCOMPLETE")
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Pronunciation submit failed: scoring/AI error")
        return _api_error("Could not score your pronunciation right now. Please try again.", "SUBMIT_SCORING_ERROR", 500)

    # ── Session flow ────────────────────────────────────────────────────────────
    if session_id:
        try:
            _ensure_pronunciation_schema()
        except SQLAlchemyError:
            db.session.rollback()
            return _api_error("The pronunciation database schema is not ready.", "DATABASE_SCHEMA_OUTDATED", 503)

        pron_session = PronunciationSession.query.filter_by(id=session_id, user_id=user_id, status="in_progress").first()
        if not pron_session:
            return _api_error("Pronunciation session not found or already completed.", "SESSION_NOT_FOUND", 404)

        turn_number = pron_session.questions_completed + 1
        attempt.session_id = session_id
        attempt.turn_number = turn_number
        pron_session.questions_completed = turn_number

        # Running average
        completed_scores = [
            a.overall_score for a in pron_session.attempts
            if a.status == "completed" and a.overall_score is not None
        ]
        
        # Priority 4: Adaptive Difficulty calculation (before adding current score for clean baseline, or including it)
        # Let's use the current score and previous score to decide the NEXT question's difficulty
        next_difficulty = pron_session.difficulty
        if len(completed_scores) >= 1 and scores["overall"] is not None:
            last_score = completed_scores[-1]
            current_score = scores["overall"]
            avg_last_two = (last_score + current_score) / 2
            
            diff_levels = ["easy", "medium", "hard"]
            current_idx = diff_levels.index(pron_session.difficulty)
            
            if avg_last_two >= 8.5 and current_idx < len(diff_levels) - 1:
                next_difficulty = diff_levels[current_idx + 1]
            elif avg_last_two <= 4.0 and current_idx > 0:
                next_difficulty = diff_levels[current_idx - 1]
            
            # Cap at original difficulty +/- 1 (we just cap to the list bounds, which is +/- 1 from medium usually)
            
        # include current attempt's score
        all_scores = completed_scores + ([scores["overall"]] if scores["overall"] is not None else [])
        pron_session.average_score = round(sum(all_scores) / len(all_scores), 1) if all_scores else None

        db.session.commit()

        if False and turn_number >= pron_session.total_questions:
            # ── Session complete ────────────────────────────────────────────────
            pron_session.status = "completed"
            pron_session.completed_at = datetime.utcnow()

            turn_results = [a.to_session_turn_dict() for a in pron_session.attempts if a.status == "completed"]
            summary = groq_service.summarize_pronunciation_session(turn_results, pron_session.difficulty)
            pron_session.average_score = summary["average_score"] or pron_session.average_score
            pron_session.summary_feedback = summary["summary_feedback"]
            pron_session.strengths_json = json.dumps(summary.get("strengths", []))
            pron_session.weaknesses_json = json.dumps(summary.get("areas_to_improve", []))
            pron_session.recommendation = summary.get("recommendation")
            pron_session.next_practice_suggestion = summary.get("next_practice_suggestion")
            
            streak_count = 0
            if pron_session.mode == "daily":
                daily_challenge = complete_daily_activity(
                    user_id,
                    PRONUNCIATION_DAILY,
                    pron_session.id,
                    result_id=attempt.id,
                )
                user = db.session.get(User, user_id)
                streak_count = user.streak_count if user else 0
            else:
                daily_challenge = None

            db.session.commit()

            return jsonify({
                "success": True,
                "done": True,
                "session_id": pron_session.id,
                "streak_count": streak_count,
                "attempt_id": attempt.public_id,
                "turn_number": turn_number,
                "total_questions": pron_session.total_questions,
                "last_turn_result": {
                    **comparison,
                    "feedback": feedback,
                    "attempt_id": attempt.public_id,
                    "attempt_number": attempt.attempt_number,
                },
                "overall_score": to_score10(pron_session.average_score),
                "average_score": to_score10(pron_session.average_score),
                "summary_feedback": pron_session.summary_feedback,
                "strengths": summary.get("strengths", []),
                "areas_to_improve": summary.get("areas_to_improve", []),
                "recommendation": summary.get("recommendation"),
                "next_practice_suggestion": summary.get("next_practice_suggestion"),
                "summary_source": summary.get("source", "groq"),
                "daily_challenge": daily_challenge,
                "turns": turn_results,
                # fields SessionResultDashboard uses
                "summary": pron_session.summary_feedback,
                "topic_title": f"{pron_session.mode.capitalize()} Practice",
                "mode": pron_session.mode,
                "difficulty": pron_session.difficulty,
                "type": "pronunciation",
                "created_at": pron_session.created_at.isoformat() if pron_session.created_at else None,
                **comparison,
                "feedback": feedback,
            })

        # ── Next question ───────────────────────────────────────────────────────
        daily_challenge = None
        streak_count = 0
        if pron_session.mode == "daily":
            daily_challenge = complete_daily_activity(
                user_id,
                PRONUNCIATION_DAILY,
                pron_session.id,
                result_id=attempt.id,
            )
            user = db.session.get(User, user_id)
            streak_count = user.streak_count if user else 0

        next_mode = pron_session.mode
        try:
            next_item = _create_item(user_id, next_mode, next_difficulty)
        except SQLAlchemyError:
            current_app.logger.exception("Could not create next pronunciation item")
            db.session.rollback()
            return _api_error("Could not generate next pronunciation item.", "GENERATION_FAILED", 503)

        return jsonify({
            "success": True,
            "done": False,
            "session_id": pron_session.id,
            "daily_challenge": daily_challenge,
            "streak_count": streak_count,
            "attempt_id": attempt.public_id,
            "turn_number": turn_number,
            "total_questions": pron_session.total_questions,
            "next_question_number": turn_number + 1,
            "last_turn_result": {
                **comparison,
                "feedback": feedback,
                "attempt_id": attempt.public_id,
                "attempt_number": attempt.attempt_number,
            },
            "next_item": _item_to_session_payload(next_item),
            "adjusted_difficulty": next_difficulty if next_difficulty != pron_session.difficulty else None,
            **comparison,
            "feedback": feedback,
        })

    # ── Standalone (non-session) flow — original behavior ──────────────────────
    db.session.commit()

    previous = (
        PronunciationAttempt.query.filter(
            PronunciationAttempt.user_id == user_id,
            PronunciationAttempt.item_id == item.id,
            PronunciationAttempt.status == "completed",
            PronunciationAttempt.public_id != attempt.public_id,
        )
        .order_by(PronunciationAttempt.completed_at.desc())
        .first()
    )
    previous_score = previous.overall_score if previous else None

    return jsonify({
        "success": True,
        "data": {
            **comparison,
            "feedback": feedback,
            "attempt_id": attempt.public_id,
            "attempt_number": attempt.attempt_number,
            "max_attempts": MAX_ATTEMPTS_PER_ITEM,
            "previous_score": previous_score,
            "improvement": round(scores["overall"] - previous_score, 1) if previous_score is not None else None,
        },
    })


@pronunciation_bp.post("/session/end")
@jwt_required()
def end_pronunciation_session():
    user_id = int(get_jwt_identity())
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id")
    session = PronunciationSession.query.filter_by(id=session_id, user_id=user_id).first_or_404()

    if session.status == "in_progress":
        turn_results = [
            a.to_session_turn_dict()
            for a in _pronunciation_attempts_for_summary(session)
        ]
        try:
            summary = groq_service.summarize_pronunciation_session(turn_results, session.difficulty)
        except Exception:
            current_app.logger.exception("Pronunciation session summary generation failed")
            summary = {
                "average_score": session.average_score,
                "summary_feedback": "Your pronunciation session is complete. Review your attempts and keep practicing.",
                "strengths": [],
                "areas_to_improve": [],
                "recommendation": "Keep practicing with another pronunciation item.",
                "next_practice_suggestion": "Try another pronunciation session.",
            }
        session.average_score = summary.get("average_score") or session.average_score
        session.summary_feedback = summary.get("summary_feedback")
        session.strengths_json = json.dumps(summary.get("strengths", []))
        session.weaknesses_json = json.dumps(summary.get("areas_to_improve", []))
        session.recommendation = summary.get("recommendation")
        session.next_practice_suggestion = summary.get("next_practice_suggestion")
        session.status = "completed"
        session.completed_at = datetime.utcnow()
        db.session.commit()
    else:
        summary = None

    return jsonify(_pronunciation_session_summary_payload(session, summary))


@pronunciation_bp.get("/history")
@jwt_required()
def attempt_history():
    user_id = int(get_jwt_identity())
    attempts = (
        PronunciationAttempt.query.filter_by(user_id=user_id, status="completed")
        .order_by(PronunciationAttempt.completed_at.desc())
        .limit(50)
        .all()
    )
    return jsonify({"success": True, "items": [attempt.to_summary_dict() for attempt in attempts]})


@pronunciation_bp.get("/history/<attempt_id>")
@jwt_required()
def attempt_detail(attempt_id):
    user_id = int(get_jwt_identity())
    attempt = PronunciationAttempt.query.filter_by(public_id=attempt_id, user_id=user_id).first()
    if not attempt:
        return _api_error("Pronunciation attempt not found.", "ATTEMPT_NOT_FOUND", 404)
    return jsonify({"success": True, "data": {"attempt": attempt.to_detail_dict()}, **attempt.to_detail_dict()})


# ─── Priority 2 & 5 & 6 Endpoints ──────────────────────────────────────────────

@pronunciation_bp.get("/insights")
@jwt_required()
def pronunciation_insights():
    """Priority 2: Problem-Sounds Tracking Over Time"""
    user_id = int(get_jwt_identity())
    
    # Get last 30 attempts
    attempts = (
        PronunciationAttempt.query.filter_by(user_id=user_id, status="completed")
        .order_by(PronunciationAttempt.completed_at.desc())
        .limit(30)
        .all()
    )
    
    tag_counts = {}
    for a in attempts:
        if a.sound_tags_json:
            tags = json.loads(a.sound_tags_json)
            for t in tags:
                tag_counts[t] = tag_counts.get(t, 0) + 1
                
    # Sort and return top 5
    sorted_tags = sorted([{"tag": k, "count": v} for k, v in tag_counts.items()], key=lambda x: x["count"], reverse=True)[:5]
    
    return jsonify({"success": True, "insights": sorted_tags})


@pronunciation_bp.get("/progress")
@jwt_required()
def pronunciation_progress():
    """Priority 5: Progress Trend Chart"""
    user_id = int(get_jwt_identity())
    
    sessions = (
        PronunciationSession.query.filter_by(user_id=user_id, status="completed")
        .filter(PronunciationSession.average_score.isnot(None))
        .order_by(PronunciationSession.completed_at.asc())
        .limit(30)
        .all()
    )
    
    data = []
    for s in sessions:
        if s.completed_at:
            data.append({
                "date": s.completed_at.strftime("%b %d"),
                "average_score": to_score10(s.average_score),
                "mode": s.mode,
                "difficulty": s.difficulty
            })
            
    return jsonify({"success": True, "progress": data})


@pronunciation_bp.get("/streak")
@jwt_required()
def get_streak():
    """Priority 6: Daily Challenge Streaks"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    if not user:
        return _api_error("User not found.", "NOT_FOUND", 404)
        
    streak_count = user.streak_count if hasattr(user, 'streak_count') else 0
    # verify streak is still active today or yesterday
    if hasattr(user, 'last_completed_date') and user.last_completed_date:
        today = today_challenge_date()
        if (today - user.last_completed_date).days > 1:
            streak_count = 0
            
    return jsonify({
        "success": True, 
        "streak_count": streak_count,
        "last_completed_date": user.last_completed_date.isoformat() if hasattr(user, 'last_completed_date') and user.last_completed_date else None
    })
