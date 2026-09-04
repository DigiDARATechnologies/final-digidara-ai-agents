from flask import Blueprint, current_app, jsonify
from flask_jwt_extended import get_jwt_identity, jwt_required
from sqlalchemy.exc import SQLAlchemyError

from ..extensions import db
from ..models import PronunciationAttempt, PronunciationItem, PronunciationSession, SpeakingSession, WritingSession
from ..services.daily_challenges import backfill_today_from_completed_sessions, today_status
from ..utils.score_utils import to_score10

dashboard_bp = Blueprint("dashboard", __name__)


def _avg(values):
    values = [v for v in values if v is not None and to_score10(v) is not None]
    return round(sum(values) / len(values), 1) if values else None


def _valid_score(value):
    """Return a canonical score or None; never turn missing data into zero."""
    if value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if numeric < 0 or numeric > 100:
        return None
    return to_score10(numeric)


def _module_selection(modules):
    valid = [module for module in modules if module["average"] is not None and module["completed"] > 0]
    if not valid:
        return {
            "best": {"key": None, "label": "No data yet", "average": None, "completed": 0, "status": "no_data"},
            "needs_work": {"key": None, "label": "Complete your first session", "average": None, "completed": 0, "status": "no_data"},
        }
    if len(valid) == 1:
        only = valid[0]
        return {
            "best": {**only, "status": "available"},
            "needs_work": {"key": None, "label": "More data needed", "average": None, "completed": 0, "status": "insufficient_data"},
        }
    highest = max(module["average"] for module in valid)
    lowest = min(module["average"] for module in valid)
    if highest == lowest:
        return {
            "best": {"key": None, "label": "Balanced performance", "average": highest, "completed": sum(m["completed"] for m in valid), "status": "tied"},
            "needs_work": {"key": None, "label": "No single weak area", "average": lowest, "completed": sum(m["completed"] for m in valid), "status": "tied"},
        }
    best = next(module for module in valid if module["average"] == highest)
    needs_work = next(module for module in valid if module["average"] == lowest)
    return {"best": {**best, "status": "available"}, "needs_work": {**needs_work, "status": "available"}}


@dashboard_bp.get("")
@jwt_required()
def get_dashboard():
    try:
        user_id = int(get_jwt_identity())

        speaking_sessions = (
            SpeakingSession.query.filter(
                SpeakingSession.user_id == user_id,
                SpeakingSession.status.in_(["completed", "ended_by_user"]),
            )
            .order_by(SpeakingSession.completed_at.desc())
            .all()
        )
        writing_sessions = (
            WritingSession.query.filter_by(user_id=user_id, status="completed")
            .order_by(WritingSession.completed_at.desc())
            .all()
        )
        pronunciation_sessions = (
            PronunciationSession.query.filter_by(user_id=user_id, status="completed")
            .order_by(PronunciationSession.completed_at.desc())
            .all()
        )
        standalone_pronunciation_attempts = (
            PronunciationAttempt.query.filter_by(user_id=user_id, status="completed")
            .filter(PronunciationAttempt.session_id.is_(None))
            .order_by(PronunciationAttempt.completed_at.desc())
            .all()
        )

        speaking_scores = [_valid_score(s.overall_score) for s in speaking_sessions]
        speaking_scores = [score for score in speaking_scores if score is not None]
        writing_scores = [_valid_score(s.overall_score) for s in writing_sessions]
        writing_scores = [score for score in writing_scores if score is not None]
        pronunciation_scores = [_valid_score(s.average_score) for s in pronunciation_sessions]
        pronunciation_scores += [_valid_score(a.overall_score) for a in standalone_pronunciation_attempts]
        pronunciation_scores = [score for score in pronunciation_scores if score is not None]

        speaking_avg = _avg(speaking_scores)
        writing_avg = _avg(writing_scores)
        pronunciation_avg = _avg(pronunciation_scores)
        speaking_best = max(speaking_scores, default=None)
        writing_best = max(writing_scores, default=None)
        pronunciation_best = max(
            pronunciation_scores,
            default=None,
        )
        modules = [
            {"key": "speaking", "label": "Speaking", "average": speaking_avg, "completed": len(speaking_scores)},
            {"key": "writing", "label": "Writing", "average": writing_avg, "completed": len(writing_scores)},
            {"key": "pronunciation", "label": "Pronunciation", "average": pronunciation_avg, "completed": len(pronunciation_scores)},
        ]
        selections = _module_selection(modules)
        today_challenge = (
            PronunciationItem.query.filter_by(user_id=user_id, practice_mode="daily")
            .order_by(PronunciationItem.created_at.desc())
            .first()
        )
        overall_avg = _avg([speaking_avg, writing_avg, pronunciation_avg])
        backfill_today_from_completed_sessions(user_id)
        today_communication_challenge = today_status(user_id)
        db.session.commit()

        recent = sorted(
            [s.to_summary_dict() for s in speaking_sessions[:5] if _valid_score(s.overall_score) is not None]
            + [s.to_summary_dict() for s in writing_sessions[:5] if _valid_score(s.overall_score) is not None]
            + [s.to_summary_dict() for s in pronunciation_sessions[:5] if _valid_score(s.average_score) is not None]
            + [a.to_summary_dict() for a in standalone_pronunciation_attempts[:5] if _valid_score(a.overall_score) is not None],
            key=lambda s: s.get("created_at") or "",
            reverse=True,
        )[:5]

        return jsonify({
            "sessions_completed": sum(module["completed"] for module in modules),
            "overall_score": to_score10(overall_avg),
            "speaking_average": to_score10(speaking_avg),
            "speaking_completed": len(speaking_scores),
            "speaking_best": to_score10(speaking_best),
            "writing_average": to_score10(writing_avg),
            "writing_completed": len(writing_scores),
            "writing_best": to_score10(writing_best),
            "pronunciation_average": to_score10(pronunciation_avg),
            "pronunciation_completed": len(pronunciation_scores),
            "pronunciation_best": to_score10(pronunciation_best),
            "best_skill": selections["best"],
            "needs_work": selections["needs_work"],
            "pronunciation_daily_ready": bool(today_challenge),
            "recent_activity": recent,
            "today_communication_challenge": today_communication_challenge,
        })
    except SQLAlchemyError:
        current_app.logger.exception("Dashboard database query failed")
        return jsonify({
            "success": False,
            "message": "Dashboard database is unavailable.",
            "error_code": "DATABASE_UNAVAILABLE",
        }), 503
    except Exception:
        current_app.logger.exception("Dashboard endpoint failed")
        return jsonify({
            "success": False,
            "message": "Dashboard data is temporarily unavailable.",
            "error_code": "DASHBOARD_UNAVAILABLE",
        }), 500
