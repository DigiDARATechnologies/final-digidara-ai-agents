"""Undoes the false "reloaded or reopened" warnings of 3 November 2026.

Until FIXED_AT the proctoring screen of a mock interview or viva was rebuilt after
every answer. Each rebuild counted as a reload: 5 integrity points and a warning,
and over the limit the test ended. Before the fix a real reload looks the same, so
all of them are forgiven. Knowledge tests never had the bug.

Nothing is deleted: each event stays, marked as not counted, with no penalty. The
sitting's integrity and warnings are worked out again from what is left, and a test
ended only by these warnings is marked as ended by a system error. Running this
twice changes nothing more.

    python -m app.proctoring.repair_false_warnings            # shows what would change
    python -m app.proctoring.repair_false_warnings --apply

Prints "@viva <submission id>" for each viva that was ended this way, for the capstone
agent to give the student new chances (app/api/viva_chances.py).
"""
import argparse
from datetime import datetime

from app import db
from app.models import ProctorEvent, ProctorSession
from app.proctoring.service import WARNING_KINDS, clean_settings

FIXED_AT = datetime(2026, 11, 3, 9, 23, 10)
AFFECTED_AGENTS = ("mock_interview_agent", "capstone_project_agent")
NOT_COUNTED = " (system error, not counted)"


def repair(apply: bool, fixed_at: datetime = FIXED_AT) -> dict:
    session = db.get_session()
    try:
        false_events = (session.query(ProctorEvent).join(ProctorSession, ProctorSession.id == ProctorEvent.session_id)
                        .filter(ProctorEvent.kind == "session_resumed", ProctorEvent.penalty > 0,
                                ProctorEvent.created_at < fixed_at, ProctorSession.agent_name.in_(AFFECTED_AGENTS))
                        .all())
        for event in false_events:
            event.penalty = 0
            event.detail = (event.detail + NOT_COUNTED)[:255]
        session.flush()
        sittings = {event.session_id for event in false_events}
        reopened = {"mock_interview_agent": 0, "capstone_project_agent": 0}
        vivas = []
        for session_id in sorted(sittings):
            sitting = session.get(ProctorSession, session_id)
            events = session.query(ProctorEvent).filter_by(session_id=session_id).all()
            sitting.integrity = max(0, 100 - sum(event.penalty for event in events))
            sitting.warnings = sum(1 for event in events if event.kind in WARNING_KINDS and not event.detail.endswith(NOT_COUNTED))
            if sitting.status == "terminated" and sitting.warnings <= clean_settings(sitting.settings)["max_warnings"]:
                sitting.status = "completed"
                sitting.result = {**(sitting.result or {}), "ended_by_system_error": True}
                reopened[sitting.agent_name] += 1
                if sitting.agent_name == "capstone_project_agent" and ":" in sitting.ref:
                    vivas.append(sitting.ref.split(":")[0])
        if apply:
            session.commit()
        else:
            session.rollback()
        return {"events": len(false_events), "sittings": len(sittings), "ended_interviews": reopened["mock_interview_agent"],
                "ended_vivas": reopened["capstone_project_agent"], "vivas": sorted(set(vivas))}
    finally:
        session.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    apply_changes = parser.parse_args().apply
    result = repair(apply_changes)
    print(("Changed: " if apply_changes else "Would change (nothing was changed): ")
          + f"{result['events']} false warnings in {result['sittings']} tests. Ended by them: "
          + f"{result['ended_interviews']} mock interviews, {result['ended_vivas']} vivas.")
    for submission_id in result["vivas"]:
        print("@viva", submission_id)
