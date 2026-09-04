from flask import Blueprint, current_app, jsonify
from flask_jwt_extended import get_jwt_identity, jwt_required
from sqlalchemy.exc import SQLAlchemyError

from ..extensions import db
from ..services.daily_challenges import backfill_today_from_completed_sessions, today_status

daily_challenges_bp = Blueprint("daily_challenges", __name__)


@daily_challenges_bp.get("/today")
@jwt_required()
def today():
    user_id = int(get_jwt_identity())
    try:
        backfill_today_from_completed_sessions(user_id)
        payload = today_status(user_id)
        db.session.commit()
        return jsonify(payload)
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Daily challenge status query failed")
        return jsonify({
            "success": False,
            "message": "Today's communication challenge could not be loaded right now.",
            "error_code": "DAILY_CHALLENGE_UNAVAILABLE",
        }), 503
