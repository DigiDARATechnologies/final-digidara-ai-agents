from datetime import datetime, timedelta, timezone
import math
from functools import wraps
from flask import current_app, g
from ..extensions import db
from ..models import RateLimitEvent
from ..models.base import as_utc
from ..utils.errors import APIError


def mysql_rate_limit(action, limit, seconds, *, limit_config=None, window_config=None):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            active_limit = int(current_app.config.get(limit_config, limit)) if limit_config else int(limit)
            active_window = int(current_app.config.get(window_config, seconds)) if window_config else int(seconds)
            now = datetime.now(timezone.utc)
            cutoff = now - timedelta(seconds=active_window)
            query = RateLimitEvent.query.filter(
                RateLimitEvent.student_id == g.student.id,
                RateLimitEvent.action == action,
                RateLimitEvent.created_at >= cutoff,
            )
            count = query.count()
            if count >= active_limit:
                oldest = query.order_by(RateLimitEvent.created_at.asc()).first()
                retry_after = min(
                    active_window,
                    max(
                        1,
                        math.ceil(((as_utc(oldest.created_at) + timedelta(seconds=active_window)) - now).total_seconds()),
                    ),
                ) if oldest else active_window
                current_app.logger.info(
                    "Application rate limit action=%s student=%s count=%s limit=%s window_seconds=%s retry_after_seconds=%s",
                    action,g.student.id,count,active_limit,active_window,retry_after,
                )
                raise APIError(
                    f"Too many requests. Please try again in {retry_after} seconds.",
                    429,"rate_limited",{"retry_after_seconds":retry_after},
                )
            response = view(*args, **kwargs)
            status = response[1] if isinstance(response, tuple) and len(response) > 1 else getattr(response, "status_code", 200)
            if int(status) < 400:
                db.session.add(RateLimitEvent(student_id=g.student.id, action=action))
                db.session.commit()
            return response
        return wrapped
    return decorator
