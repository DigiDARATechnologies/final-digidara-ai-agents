from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from ..models import PronunciationAttempt, PronunciationSession, SpeakingSession, WritingSession

history_bp = Blueprint("history", __name__)


@history_bp.get("")
@jwt_required()
def list_history():
    user_id = int(get_jwt_identity())
    try:
        page = max(1, int(request.args.get("page", 1)))
    except (TypeError, ValueError):
        page = 1
    try:
        per_page = int(request.args.get("per_page", 10))
    except (TypeError, ValueError):
        per_page = 10
    per_page = max(1, min(per_page, 50))
    item_type = (request.args.get("type") or "all").strip().lower()
    if item_type not in {"all", "speaking", "writing", "pronunciation"}:
        return jsonify({"success": False, "message": "type must be all, speaking, writing or pronunciation", "error_code": "INVALID_TYPE"}), 400

    speaking = []
    writing = []
    pronunciation_sessions = []
    standalone_attempts = []

    if item_type in {"all", "speaking"}:
        speaking = SpeakingSession.query.filter(
            SpeakingSession.user_id == user_id,
            SpeakingSession.status.in_(["completed", "ended_by_user"]),
        ).all()
    if item_type in {"all", "writing"}:
        writing = WritingSession.query.filter_by(user_id=user_id, status="completed").all()
    if item_type in {"all", "pronunciation"}:
        # Prefer session-based records; fall back to standalone attempts
        pronunciation_sessions = PronunciationSession.query.filter_by(user_id=user_id, status="completed").all()
        # Also include standalone attempts (no session_id) for backward compat
        standalone_attempts = (
            PronunciationAttempt.query.filter(
                PronunciationAttempt.user_id == user_id,
                PronunciationAttempt.status == "completed",
                PronunciationAttempt.session_id.is_(None),
            ).all()
        )

    items = (
        [s.to_summary_dict() for s in speaking]
        + [s.to_summary_dict() for s in writing]
        + [s.to_summary_dict() for s in pronunciation_sessions]
        + [a.to_summary_dict() for a in standalone_attempts]
    )
    items.sort(key=lambda s: s["created_at"] or "", reverse=True)
    total = len(items)
    start = (page - 1) * per_page
    end = start + per_page
    page_items = items[start:end]
    pages = (total + per_page - 1) // per_page if total else 1

    return jsonify({
        "success": True,
        "items": page_items,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "pages": pages,
            "has_next": page < pages,
            "has_prev": page > 1,
        },
    })


@history_bp.get("/<int:session_id>")
@jwt_required()
def unified_detail(session_id):
    user_id = int(get_jwt_identity())
    speaking = SpeakingSession.query.filter_by(id=session_id, user_id=user_id).first()
    if speaking:
        return jsonify({"success": True, "data": {"session": speaking.to_detail_dict()}})
    writing = WritingSession.query.filter_by(id=session_id, user_id=user_id).first()
    if writing:
        return jsonify({"success": True, "data": {"session": writing.to_detail_dict()}})
    pron_session = PronunciationSession.query.filter_by(id=session_id, user_id=user_id).first()
    if pron_session:
        return jsonify({"success": True, "data": {"session": pron_session.to_detail_dict()}})
    pronunciation = PronunciationAttempt.query.filter_by(id=session_id, user_id=user_id).first()
    if pronunciation:
        return jsonify({"success": True, "data": {"session": pronunciation.to_detail_dict()}})
    return jsonify({"success": False, "message": "Session not found.", "error_code": "SESSION_NOT_FOUND"}), 404


@history_bp.get("/speaking/<int:session_id>")
@jwt_required()
def speaking_detail(session_id):
    user_id = int(get_jwt_identity())
    session = SpeakingSession.query.filter_by(id=session_id, user_id=user_id).first_or_404()
    return jsonify({"success": True, "data": {"session": session.to_detail_dict()}, **session.to_detail_dict()})


@history_bp.get("/writing/<int:session_id>")
@jwt_required()
def writing_detail(session_id):
    user_id = int(get_jwt_identity())
    session = WritingSession.query.filter_by(id=session_id, user_id=user_id).first_or_404()
    return jsonify({"success": True, "data": {"session": session.to_detail_dict()}, **session.to_detail_dict()})


@history_bp.get("/pronunciation/<int:attempt_id>")
@jwt_required()
def pronunciation_detail(attempt_id):
    user_id = int(get_jwt_identity())
    # Check if it's a session first
    pron_session = PronunciationSession.query.filter_by(id=attempt_id, user_id=user_id).first()
    if pron_session:
        return jsonify({"success": True, "data": {"session": pron_session.to_detail_dict()}, **pron_session.to_detail_dict()})
    attempt = PronunciationAttempt.query.filter_by(id=attempt_id, user_id=user_id).first_or_404()
    return jsonify({"success": True, "data": {"session": attempt.to_detail_dict()}, **attempt.to_detail_dict()})
