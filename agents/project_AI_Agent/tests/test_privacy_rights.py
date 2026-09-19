"""DPDP data-subject rights: export and erasure of a learner's own data."""
from app.db.models import ProjectAssignment, Student, Submission


def test_export_requires_verified_caller(client, database):
    response = client.post("/api/privacy/export", json={"email": "learner@example.test"})
    assert response.status_code == 401


def test_export_unknown_email_is_not_found(client, database):
    response = client.post(
        "/api/privacy/export",
        json={"email": "nobody@example.test"},
        headers={"x-digidara-user-id": "gateway-user-1"},
    )
    assert response.status_code == 404


def test_export_returns_profile_and_assignments(client, database):
    response = client.post(
        "/api/privacy/export",
        json={"email": "learner@example.test"},
        headers={"x-digidara-user-id": "gateway-user-1"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["profile"]["email"] == "learner@example.test"
    assert body["profile"]["name"] == "Learner"
    assert len(body["project_assignments"]) == 1
    assert body["project_assignments"][0]["thread_id"] == "thread"


def test_erase_requires_verified_caller(client, database):
    response = client.request("DELETE", "/api/privacy/erase", json={"email": "learner@example.test"})
    assert response.status_code == 401


def test_erase_anonymizes_profile_and_submission_text(client, database):
    with database() as session:
        session.add(Submission(
            id="submission",
            assignment_id="assignment",
            docx_path="report.docx",
            zip_path="source.zip",
            feedback_text="Detailed personal feedback",
            review_markdown="# Review",
        ))
        session.commit()

    response = client.request(
        "DELETE",
        "/api/privacy/erase",
        json={"email": "learner@example.test"},
        headers={"x-digidara-user-id": "gateway-user-1"},
    )
    assert response.status_code == 200
    assert response.json()["id"] == "student"

    with database() as session:
        student = session.get(Student, "student")
        assert student.name == "Erased User"
        assert student.email == "erased-student@erased.invalid"
        assert student.phone is None

        assignment = session.get(ProjectAssignment, "assignment")
        assert assignment.qa_conversation_json is None

        submission = session.get(Submission, "submission")
        assert submission.feedback_text is None
        assert submission.review_markdown is None

    # A second export request against the now-anonymized email finds nothing.
    followup = client.post(
        "/api/privacy/export",
        json={"email": "learner@example.test"},
        headers={"x-digidara-user-id": "gateway-user-1"},
    )
    assert followup.status_code == 404
