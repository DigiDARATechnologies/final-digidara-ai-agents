"""New chances for vivas ended by the false proctoring warnings of 3 November 2026
(orchestrator app/proctoring/repair_false_warnings.py). Uses the same second chances
as the run fix (app/api/regrade.py): a notification and 3 more submissions, even past
the deadline, and a student who had passed keeps that pass.

Reads "@viva <submission id>" lines. Shows what would change unless given --apply,
and running it twice changes nothing more.
"""
from __future__ import annotations

import argparse
import sys

from app.api.regrade import CHANCES, _passed, _score
from app.db.database import get_session
from app.db.models import ProjectAssignment, ProjectRegrade, Submission

REASON = "viva_proctoring"


def grant(submission_ids: list[str], apply: bool) -> int:
    session = get_session()
    try:
        granted = 0
        for assignment_id in {row.assignment_id for row in session.query(Submission).filter(Submission.id.in_(submission_ids)).all()}:
            assignment = session.get(ProjectAssignment, assignment_id)
            if assignment is None or session.query(ProjectRegrade).filter_by(assignment_id=assignment_id, reason=REASON).first():
                continue
            submissions = session.query(Submission).filter_by(assignment_id=assignment_id).order_by(Submission.submitted_at).all()
            passed = [submission for submission in submissions if _passed(submission)]
            hit = [submission for submission in submissions if submission.id in submission_ids]
            kept = passed[-1] if passed else hit[-1]
            row = session.get(ProjectRegrade, assignment_id)
            if row is None:
                row = ProjectRegrade(assignment_id=assignment_id, student_id=assignment.student_id, submission_id=kept.id,
                                     original_passed=bool(passed), original_score=_score(kept), chances_left=0)
                session.add(row)
            row.chances_left = max(row.chances_left or 0, CHANCES)
            row.reason = REASON
            granted += 1
        if apply:
            session.commit()
        else:
            session.rollback()
        return granted
    finally:
        session.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    apply_changes = parser.parse_args().apply
    ids = [line.split()[1] for line in sys.stdin if line.startswith("@viva ") and len(line.split()) == 2]
    count = grant(ids, apply_changes) if ids else 0
    print(("Gave" if apply_changes else "Would give") + f" {count} capstone project(s) {CHANCES} new chances.")
