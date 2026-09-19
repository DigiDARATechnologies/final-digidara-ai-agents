"""Persistence helpers for auditable interview focus-loss episodes."""

import db
from policies import integrity_flagged


def focus_summary(interview_id):
    row, _ = db.query(
        """SELECT COUNT(*) AS focus_loss_count,
                  COALESCE(SUM(
                    COALESCE(
                      away_seconds,
                      GREATEST(0, TIMESTAMPDIFF(SECOND, left_at, NOW(6)))
                    )
                  ), 0) AS focus_loss_total_seconds
           FROM interview_focus_events
           WHERE interview_id = %s""",
        (interview_id,),
        fetchone=True,
    )
    count = int(row["focus_loss_count"] or 0) if row else 0
    seconds = int(row["focus_loss_total_seconds"] or 0) if row else 0
    return {
        "focus_loss_count": count,
        "focus_loss_total_seconds": seconds,
        "integrity_flagged": integrity_flagged(count, seconds),
    }


def finalize_open_focus_events(interview_id):
    """Close any event whose browser return request never reached the server."""
    db.query(
        """UPDATE interview_focus_events
           SET returned_at = NOW(6),
               away_seconds = GREATEST(
                 0, TIMESTAMPDIFF(SECOND, left_at, NOW(6))
               )
           WHERE interview_id = %s AND returned_at IS NULL""",
        (interview_id,),
    )
    return focus_summary(interview_id)
