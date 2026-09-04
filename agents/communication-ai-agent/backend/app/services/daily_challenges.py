from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from ..extensions import db
from ..models import (
    DailyChallengeProgress,
    DailyChallengeSummary,
    PronunciationAttempt,
    PronunciationSession,
    SpeakingSession,
    User,
    WritingSession,
)

try:
    APP_TIMEZONE = ZoneInfo("Asia/Kolkata")
except Exception:
    APP_TIMEZONE = timezone(timedelta(hours=5, minutes=30), name="Asia/Kolkata")

SPEAKING_DAILY = "speaking_daily_conversation"
WRITING_DAILY = "writing_daily_challenge"
PRONUNCIATION_DAILY = "pronunciation_daily_challenge"

ACTIVITY_CONFIG = {
    SPEAKING_DAILY: {
        "module": "speaking",
        "title": "Daily Speaking Challenge",
        "xp_reward": 30,
        "route": "/speaking?mode=daily",
    },
    WRITING_DAILY: {
        "module": "writing",
        "title": "Daily Writing Challenge",
        "xp_reward": 30,
        "route": "/writing?mode=daily",
    },
    PRONUNCIATION_DAILY: {
        "module": "pronunciation",
        "title": "Daily Pronunciation Challenge",
        "xp_reward": 20,
        "route": "/pronunciation?mode=daily",
    },
}

ACTIVITY_ORDER = [SPEAKING_DAILY, WRITING_DAILY, PRONUNCIATION_DAILY]
DAILY_BONUS_XP = 20
ROTATION_ANCHOR_DATE = date(2026, 8, 28)

def selected_activity_type(challenge_date=None):
    """Return the single challenge assigned for a day: speaking, writing, pronunciation, repeat."""
    challenge_date = challenge_date or today_challenge_date()
    return ACTIVITY_ORDER[(challenge_date - ROTATION_ANCHOR_DATE).days % len(ACTIVITY_ORDER)]


def today_challenge_date():
    return datetime.now(APP_TIMEZONE).date()


def challenge_day_bounds(challenge_date=None):
    challenge_date = challenge_date or today_challenge_date()
    start_local = datetime.combine(challenge_date, time.min, tzinfo=APP_TIMEZONE)
    end_local = datetime.combine(challenge_date, time.max, tzinfo=APP_TIMEZONE)
    return (
        start_local.astimezone(timezone.utc).replace(tzinfo=None),
        end_local.astimezone(timezone.utc).replace(tzinfo=None),
    )


def _now():
    return datetime.utcnow()


def _summary(user_id, challenge_date):
    summary = DailyChallengeSummary.query.filter_by(user_id=user_id, challenge_date=challenge_date).first()
    if not summary:
        summary = DailyChallengeSummary(
            user_id=user_id,
            challenge_date=challenge_date,
            completed_count=0,
            total_count=1,
            all_completed=False,
            bonus_xp_awarded=0,
        )
        db.session.add(summary)
        db.session.flush()
    return summary


def _progress(user_id, challenge_date, activity_type, for_update=False):
    query = DailyChallengeProgress.query.filter_by(
        user_id=user_id,
        challenge_date=challenge_date,
        activity_type=activity_type,
    )
    if for_update:
        query = query.with_for_update()
    progress = query.first()
    if not progress:
        progress = DailyChallengeProgress(
            user_id=user_id,
            challenge_date=challenge_date,
            activity_type=activity_type,
            status="not_started",
            xp_awarded=0,
        )
        db.session.add(progress)
        db.session.flush()
    return progress


def ensure_today_records(user_id, challenge_date=None):
    challenge_date = challenge_date or today_challenge_date()
    _progress(user_id, challenge_date, selected_activity_type(challenge_date))
    _refresh_summary(user_id, challenge_date)
    return challenge_date


def _refresh_summary(user_id, challenge_date):
    selected = selected_activity_type(challenge_date)
    progress = _progress(user_id, challenge_date, selected)
    completed_count = 1 if progress.status == "completed" else 0
    summary = _summary(user_id, challenge_date)
    summary.completed_count = completed_count
    summary.total_count = 1
    summary.all_completed = completed_count == 1
    summary.completed_at = progress.completed_at if summary.all_completed else None
    return summary


def mark_activity_started(user_id, activity_type, session_id=None, challenge_date=None):
    if activity_type not in ACTIVITY_CONFIG:
        raise ValueError("Unknown daily challenge activity")
    challenge_date = challenge_date or today_challenge_date()
    ensure_today_records(user_id, challenge_date)
    progress = _progress(user_id, challenge_date, activity_type)
    if progress.status == "not_started":
        progress.status = "in_progress"
        progress.started_at = _now()
    if session_id and not progress.source_session_id:
        progress.source_session_id = session_id
    db.session.flush()
    return progress


def _validate_speaking(user_id, session_id):
    session = SpeakingSession.query.filter_by(id=session_id, user_id=user_id).first()
    if not session or session.mode != "daily_conversation" or session.status not in {"in_progress", "completed"}:
        return False, session
    completed_turns = [turn for turn in session.turns if turn.user_answer and turn.feedback_json]
    return len(completed_turns) >= 1, session


def _validate_writing(user_id, session_id):
    session = WritingSession.query.filter_by(id=session_id, user_id=user_id).first()
    if not session or session.mode != "daily" or session.status not in {"in_progress", "completed"}:
        return False, session
    completed_turns = [turn for turn in session.turns if turn.user_response and turn.feedback_json]
    return len(completed_turns) >= 1, session


def _validate_pronunciation(user_id, session_id):
    session = PronunciationSession.query.filter_by(id=session_id, user_id=user_id).first()
    if not session:
        return False, None
    if session.mode != "daily" or session.status not in {"in_progress", "completed"}:
        return False, session
    completed_attempts = [
        attempt for attempt in session.attempts
        if attempt.status == "completed" and attempt.feedback_json and attempt.comparison_json
    ]
    required = max(1, int(session.total_questions or 1))
    if len(completed_attempts) < required:
        return False, session
    return True, session


def _validate_completion(user_id, activity_type, session_id):
    if activity_type == SPEAKING_DAILY:
        return _validate_speaking(user_id, session_id)
    if activity_type == WRITING_DAILY:
        return _validate_writing(user_id, session_id)
    if activity_type == PRONUNCIATION_DAILY:
        return _validate_pronunciation(user_id, session_id)
    raise ValueError("Unknown daily challenge activity")


def _update_daily_streak_once(user_id, challenge_date):
    user = db.session.get(User, user_id)
    if not user or user.last_completed_date == challenge_date:
        return
    previous_date = user.last_completed_date
    if previous_date and (challenge_date - previous_date).days == 1:
        user.streak_count += 1
    else:
        user.streak_count = 1
    user.last_completed_date = challenge_date


def _award_user_xp(user_id, amount):
    if not amount:
        return
    user = db.session.get(User, user_id)
    if not user:
        return
    user.total_xp = int(user.total_xp or 0) + int(amount)


def complete_daily_activity(user_id, activity_type, session_id, result_id=None, challenge_date=None):
    if activity_type not in ACTIVITY_CONFIG:
        raise ValueError("Unknown daily challenge activity")
    challenge_date = challenge_date or today_challenge_date()
    valid, session = _validate_completion(user_id, activity_type, session_id)
    if not valid:
        return today_status(user_id, challenge_date=challenge_date)

    ensure_today_records(user_id, challenge_date)
    progress = _progress(user_id, challenge_date, activity_type, for_update=True)
    if progress.status != "completed":
        progress.status = "completed"
        progress.source_session_id = session_id
        progress.source_result_id = result_id
        progress.completed_at = _now()
        if not progress.started_at:
            progress.started_at = progress.completed_at
        if not progress.xp_awarded:
            progress.xp_awarded = ACTIVITY_CONFIG[activity_type]["xp_reward"]
            _award_user_xp(user_id, progress.xp_awarded)

    summary = _refresh_summary(user_id, challenge_date)
    if activity_type == selected_activity_type(challenge_date) and summary.completed_count == 1:
        if not summary.all_completed:
            summary.all_completed = True
            summary.completed_at = _now()
        if not summary.bonus_xp_awarded:
            summary.bonus_xp_awarded = DAILY_BONUS_XP
            _award_user_xp(user_id, DAILY_BONUS_XP)
        _update_daily_streak_once(user_id, challenge_date)
    db.session.flush()
    return today_status(user_id, challenge_date=challenge_date)


def _activity_payload(progress):
    config = ACTIVITY_CONFIG[progress.activity_type]
    return {
        "activity_type": progress.activity_type,
        "module": config["module"],
        "title": config["title"],
        "status": progress.status,
        "completed": progress.status == "completed",
        "xp_reward": config["xp_reward"],
        "xp_awarded": progress.xp_awarded,
        "route": config["route"],
        "source_session_id": progress.source_session_id,
        "source_result_id": progress.source_result_id,
        "started_at": progress.started_at.isoformat() if progress.started_at else None,
        "completed_at": progress.completed_at.isoformat() if progress.completed_at else None,
    }


def today_status(user_id, challenge_date=None):
    challenge_date = challenge_date or today_challenge_date()
    ensure_today_records(user_id, challenge_date)
    summary = _refresh_summary(user_id, challenge_date)
    selected = selected_activity_type(challenge_date)
    activities = [_activity_payload(_progress(user_id, challenge_date, selected))]
    user = db.session.get(User, user_id)
    activity_xp_awarded = sum(activity["xp_awarded"] for activity in activities)
    return {
        "challenge_date": challenge_date.isoformat(),
        "completed_count": summary.completed_count,
        "total_count": summary.total_count,
        "all_completed": summary.all_completed,
        "bonus_awarded": bool(summary.bonus_xp_awarded),
        "daily_bonus_awarded": bool(summary.bonus_xp_awarded),
        "daily_bonus_xp": DAILY_BONUS_XP,
        "bonus_xp_awarded": summary.bonus_xp_awarded,
        "activity_xp_awarded": activity_xp_awarded,
        "total_xp_awarded_today": activity_xp_awarded + int(summary.bonus_xp_awarded or 0),
        "user_total_xp": int(user.total_xp or 0) if user else 0,
        "streak_count": int(user.streak_count or 0) if user else 0,
        "activities": activities,
    }


def activity_status(user_id, activity_type, challenge_date=None):
    if activity_type not in ACTIVITY_CONFIG:
        raise ValueError("Unknown daily challenge activity")
    status = today_status(user_id, challenge_date=challenge_date)
    activity = next(
        (item for item in status["activities"] if item["activity_type"] == activity_type),
        None,
    )
    if not activity:
        config = ACTIVITY_CONFIG[activity_type]
        activity = {
            "activity_type": activity_type,
            "module": config["module"],
            "title": config["title"],
            "status": "not_started",
            "completed": False,
            "xp_reward": config["xp_reward"],
            "xp_awarded": 0,
            "route": config["route"],
        }
    return {
        "success": True,
        "challenge_date": status["challenge_date"],
        "activity_type": activity_type,
        "module": activity["module"],
        "title": activity["title"],
        "status": activity["status"],
        "completed": activity["completed"],
        "completed_today": activity["completed"],
        "xp_reward": activity["xp_reward"],
        "xp_awarded": activity["xp_awarded"],
        "route": activity["route"],
        "daily_bonus_xp": status["daily_bonus_xp"],
        "all_completed": status["all_completed"],
        "completed_count": status["completed_count"],
        "total_count": status["total_count"],
    }


def backfill_today_from_completed_sessions(user_id, challenge_date=None):
    challenge_date = challenge_date or today_challenge_date()
    start_utc, end_utc = challenge_day_bounds(challenge_date)

    speaking = (
        SpeakingSession.query.filter(
            SpeakingSession.user_id == user_id,
            SpeakingSession.mode == "daily_conversation",
            SpeakingSession.status == "completed",
            SpeakingSession.completed_at >= start_utc,
            SpeakingSession.completed_at <= end_utc,
        )
        .order_by(SpeakingSession.completed_at.desc())
        .first()
    )
    if speaking:
        complete_daily_activity(user_id, SPEAKING_DAILY, speaking.id, challenge_date=challenge_date)

    writing = (
        WritingSession.query.filter(
            WritingSession.user_id == user_id,
            WritingSession.mode == "daily",
            WritingSession.status == "completed",
            WritingSession.completed_at >= start_utc,
            WritingSession.completed_at <= end_utc,
        )
        .order_by(WritingSession.completed_at.desc())
        .first()
    )
    if writing:
        complete_daily_activity(user_id, WRITING_DAILY, writing.id, challenge_date=challenge_date)

    pronunciation = (
        PronunciationSession.query.filter(
            PronunciationSession.user_id == user_id,
            PronunciationSession.mode == "daily",
            PronunciationSession.status == "completed",
            PronunciationSession.completed_at >= start_utc,
            PronunciationSession.completed_at <= end_utc,
        )
        .order_by(PronunciationSession.completed_at.desc())
        .first()
    )
    if pronunciation:
        last_attempt = (
            PronunciationAttempt.query.filter_by(session_id=pronunciation.id, status="completed")
            .order_by(PronunciationAttempt.completed_at.desc())
            .first()
        )
        complete_daily_activity(
            user_id,
            PRONUNCIATION_DAILY,
            pronunciation.id,
            result_id=last_attempt.id if last_attempt else None,
            challenge_date=challenge_date,
        )
    db.session.flush()
