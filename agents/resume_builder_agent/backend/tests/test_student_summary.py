"""Phase 2 readiness skill: get_student_summary."""
from app.extensions import db
from app.models import AtsAnalysis, Resume, User

HEADERS = {"X-Digidara-User-Id": "platform-user-1"}


def _invoke(client, headers=HEADERS):
    return client.post("/api/invoke", json={"action": "get_student_summary", "payload": {}}, headers=headers)


def test_requires_verified_identity(client):
    assert _invoke(client, headers={}).status_code == 401


def test_learner_without_resumes_has_no_score(client, app):
    assert _invoke(client).get_json()["score"] is None


def test_resume_without_ats_check_asks_for_one(client, app):
    db.session.add(User(user_id="platform-user-1"))
    db.session.add(Resume(user_id="platform-user-1", title="My resume"))
    db.session.commit()
    body = _invoke(client).get_json()
    assert body["score"] is None and body["gaps"] == ["Run an ATS check on your resume"]
    assert body["metrics"]["resumes"] == 1


def test_best_ats_score_is_the_score(client, app):
    db.session.add(User(user_id="platform-user-1"))
    resume = Resume(user_id="platform-user-1", title="My resume", ats_score=55, job_match_score=70)
    db.session.add(resume)
    db.session.flush()
    for score in (55, 78):
        db.session.add(AtsAnalysis(
            resume_id=resume.id, user_id="platform-user-1", analysis_type="ats", final_score=score,
            scoring_version="v2", matched_requirements=["Python", {"requirement": "SQL"}],
            missing_requirements=["Docker"],
        ))
    db.session.commit()
    body = _invoke(client).get_json()
    assert body["score"] == 78.0
    assert body["strengths"] == ["Python", "SQL"] and body["gaps"] == ["Docker"]
    assert body["metrics"]["ats_checks"] == 2 and body["metrics"]["best_job_match"] == 70


def test_another_learners_resumes_are_never_read(client, app):
    db.session.add(User(user_id="someone-else"))
    db.session.add(Resume(user_id="someone-else", title="Theirs", ats_score=90))
    db.session.commit()
    assert _invoke(client).get_json()["score"] is None
