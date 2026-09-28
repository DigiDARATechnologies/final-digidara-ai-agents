"""A dead worker must not lock a student out of submitting, and a student can ask about an image."""
import base64
import threading
from datetime import datetime, timedelta, timezone

from app import config
from app.api import routes
from app.db.models import ProjectAssignment, Submission, SubmissionStatus


def upload(client):
    return client.post("/api/submission/upload", data={"thread_id": "thread"},
                       files={"docx_file": ("report.docx", b"fixture"), "zip_file": ("source.zip", b"fixture")})


def stuck_submission(database, age_minutes):
    with database() as session:
        session.add(Submission(id="stuck", assignment_id="assignment", docx_path="d", zip_path="z", status=SubmissionStatus.processing,
                               submitted_at=datetime.now(timezone.utc) - timedelta(minutes=age_minutes)))
        session.commit()


# ------------------------------------------------------- submissions ----------

def test_a_submission_still_being_graded_blocks_a_second_one(client, workflow, database):
    stuck_submission(database, age_minutes=1)
    response = upload(client)
    assert response.status_code == 409 and "still being graded" in response.json()["detail"]


def test_a_submission_stuck_from_a_dead_worker_no_longer_blocks_the_student(client, workflow, database):
    stuck_submission(database, age_minutes=config.SUBMISSION_STALE_MINUTES + 1)
    assert upload(client).status_code == 200
    with database() as session:
        old = session.get(Submission, "stuck")
        assert old.status == SubmissionStatus.error and "interrupted" in old.feedback_text


def test_grading_runs_off_the_event_loop_so_a_long_grade_cannot_freeze_the_worker(client, workflow, monkeypatch):
    seen = {}

    def grade(state):
        seen["thread"] = threading.current_thread()
        return {"status": "graded", "passed": True, "final_score": 85, "feedback": "ok"}

    monkeypatch.setattr(routes, "_run_submission", grade)
    assert upload(client).status_code == 200
    assert seen["thread"] is not threading.main_thread()


# --------------------------------------------------------- image questions ----

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 32


def ask(client, **extra):
    data = {"action": "ask_project_question", "thread_id": "thread", "question": "What does this error mean?"}
    return client.post("/api/invoke", data=data, **extra)


def test_an_image_attached_to_a_question_is_read_and_the_answer_uses_it(client, monkeypatch):
    seen = {}

    def describe(**kwargs):
        seen["image"] = kwargs["image_data_url"]
        return "A terminal showing: ModuleNotFoundError: No module named 'flask'"

    def answer(thread_id, question, extra_context=None):
        seen["context"] = extra_context
        return {"answer": "Install flask with pip.", "tools_used": []}

    monkeypatch.setattr(routes, "call_text", describe)
    monkeypatch.setattr(routes, "ask_project_question", answer)
    response = ask(client, files={"attachment": ("error.png", PNG, "image/png")})
    assert response.status_code == 200 and response.json()["answer"] == "Install flask with pip."
    assert seen["image"] == "data:image/png;base64," + base64.b64encode(PNG).decode()
    assert "[Image attached by the student]" in seen["context"] and "ModuleNotFoundError" in seen["context"]


def test_a_question_with_no_attachment_still_works_through_multipart(client, monkeypatch):
    monkeypatch.setattr(routes, "ask_project_question", lambda thread_id, question, extra_context=None: {"answer": f"ctx={extra_context}", "tools_used": []})
    assert ask(client, files={"unused": ("x.txt", b"x")}).json()["answer"] == "ctx=None"


def test_bad_attachments_and_empty_questions_are_refused_clearly(client, monkeypatch):
    monkeypatch.setattr(routes, "ask_project_question", lambda *a, **k: {"answer": "x", "tools_used": []})
    assert ask(client, files={"attachment": ("notes.txt", b"hello", "text/plain")}).status_code == 415
    assert ask(client, files={"attachment": ("empty.png", b"", "image/png")}).status_code == 400
    blank = client.post("/api/invoke", data={"action": "ask_project_question", "thread_id": "thread", "question": "  "})
    assert blank.status_code == 400
    other = client.post("/api/invoke", data={"action": "nope"}, files={"z": ("z.txt", b"z")})
    assert other.status_code == 400 and "ask_project_question" in other.json()["detail"]
