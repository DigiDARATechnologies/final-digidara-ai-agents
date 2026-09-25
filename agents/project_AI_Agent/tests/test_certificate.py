"""The capstone certificate: only after BOTH the score and the viva pass; the name is
editable in the preview until the student confirms (OK); then it can be downloaded."""
import base64
import re
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from app.db.models import ProjectAssignment, Submission, SubmissionStatus
from app.reports.certificate import (
    assemble_certificate_data,
    build_certificate_pdf,
    certificate_id,
    clean_recipient_name,
    project_rating,
    render_preview_jpeg,
)

ISSUED = datetime(2026, 9, 25, 9, 0, tzinfo=timezone.utc)


def printed(pdf):
    """Just the text the certificate draws (the Tj operators), not the template image's bytes."""
    return b"\n".join(re.findall(rb"\(((?:[^()\\]|\\.)*)\) Tj", pdf))


def sample(**overrides):
    data = {
        "name": "Asha Rao", "project_title": "Inventory Tracker with Low-Stock Alerts",
        "summary": "A web application that lets small shops track daily stock and see what is running low.",
        "technology": "Python", "skills": ["REST API design", "SQL data modelling"],
        "project_rating": "Good", "viva_rating": "Average", "issued_at": ISSUED, "certificate_id": "DDT-CAP-2026-AB12CD34",
    }
    data.update(overrides)
    return data


# ------------------------------------------------------------------ the PDF ---

def test_the_certificate_is_one_page_carrying_the_student_the_project_and_the_ratings():
    pdf = build_certificate_pdf(sample())
    assert pdf.startswith(b"%PDF-") and len(re.findall(rb"/Type /Page\b(?!s)", pdf)) == 1
    for text in (b"ASHA RAO", b"INVENTORY TRACKER WITH LOW-STOCK", b"ALERTS", b"capstone project", b"Technology: Python",
                 b"REST API design", b"PROJECT: GOOD", b"VIVA VOCE: AVERAGE", b"25 September 2026", b"DDT-CAP-2026-AB12CD34"):
        assert text in pdf, text


def test_no_marks_or_percentages_are_printed_on_the_certificate():
    text = printed(build_certificate_pdf(sample()))
    assert b"Certificate ID" in text                      # the extraction really sees the printed text
    assert b"%" not in text and not re.search(rb"\d+\s*(/|of|out of)\s*\d+", text)


def test_the_certificate_is_built_on_the_digidara_template_with_its_logo():
    from app.reports.certificate import TEMPLATE
    assert TEMPLATE.exists()
    assert build_certificate_pdf(sample()).count(b"/Subtype /Image") == 1      # the template artwork: logo, seals, signature


def test_long_names_and_titles_and_hostile_text_still_produce_a_valid_pdf():
    pdf = build_certificate_pdf(sample(name="V" * 60, project_title="Very " * 40 + "Long Title", summary="Words " * 200,
                                       skills=["skill " * 20] * 6, technology="日本語 <b>x</b>"))
    assert pdf.startswith(b"%PDF-") and len(re.findall(rb"/Type /Page\b(?!s)", pdf)) == 1
    assert b"?" in printed(pdf)                           # the CJK technology name degrades to "?", it does not break the file


def test_the_preview_is_the_same_page_as_a_jpeg():
    jpeg = render_preview_jpeg(build_certificate_pdf(sample()))
    assert jpeg[:2] == b"\xff\xd8" and 20_000 < len(jpeg) < 600_000


# ----------------------------------------------------------- name and rating ---

@pytest.mark.parametrize("raw,clean", [("  Asha   Rao ", "Asha Rao"), ("D'Souza-Iyer", "D'Souza-Iyer"), ("A. R. Rahman", "A. R. Rahman"), ("José Núñez", "José Núñez")])
def test_valid_names_are_tidied(raw, clean):
    assert clean_recipient_name(raw) == clean


@pytest.mark.parametrize("raw", ["", "   ", "A", "x" * 61, "Asha<script>", "Asha 123", "日本語", "@asha", None])
def test_invalid_names_are_refused_with_a_reason(raw):
    with pytest.raises(ValueError) as error:
        clean_recipient_name(raw)
    assert str(error.value)


def test_project_rating_and_certificate_id():
    assert [project_rating(s) for s in (100, 85, 84.9, 70)] == ["Good", "Good", "Average", "Average"] and project_rating(None) == "Average"
    assert certificate_id("abcdef1234567890", ISSUED) == "DDT-CAP-2026-ABCDEF12"


def test_data_is_project_specific_and_uses_the_attempt_that_passed():
    assignment = SimpleNamespace(topic_json={"title": "Chat Bot", "summary": "Answers FAQs.", "medium": "Python", "skills_applied": ["NLP", " "]},
                                 medium=SimpleNamespace(value="python"))
    submission = SimpleNamespace(id="s1234567", score_json={"final_score": 91}, viva_score=9, viva_questions_json=[],
                                 viva_attempts_json=[{"attempt": 1, "rating": "Bad", "passed": False}, {"attempt": 2, "rating": "Good", "passed": True}])
    data = assemble_certificate_data(assignment, None, submission, "Asha Rao", ISSUED)
    assert (data["project_title"], data["technology"], data["skills"]) == ("Chat Bot", "Python", ["NLP"])
    assert (data["project_rating"], data["viva_rating"], data["certificate_id"]) == ("Good", "Good", "DDT-CAP-2026-S1234567")


# ------------------------------------------------------------------ the API ---

def seed(database, *, status=SubmissionStatus.graded, passed=True, viva_passed=True, certificate=None):
    with database() as session:
        assignment = session.get(ProjectAssignment, "assignment")
        assignment.topic_json = {"id": "one", "title": "Static Login Page", "summary": "A responsive login page.",
                                 "medium": "HTML/CSS/JS", "skills_applied": ["Form validation", "Responsive layout"]}
        session.add(Submission(
            id="sub1", assignment_id="assignment", docx_path="d", zip_path="z", status=status,
            score_json={"final_score": 88, "passed": passed}, viva_score=8, viva_passed=viva_passed,
            viva_attempts_json=[{"attempt": 1, "correct": 8, "total": 10, "rating": "Good", "passed": True, "questions": [], "answers": []}],
            certificate_json=certificate,
        ))
        session.commit()


def call(client, action, **payload):
    return client.post("/api/invoke", json={"action": action, "payload": {"submission_id": "sub1", **payload}})


@pytest.mark.parametrize("kwargs", [{"status": SubmissionStatus.pending_viva}, {"status": SubmissionStatus.needs_revision},
                                    {"passed": False}, {"viva_passed": False}, {"viva_passed": None}])
@pytest.mark.parametrize("action", ["preview_certificate", "confirm_certificate", "download_certificate"])
def test_no_certificate_until_both_the_score_and_the_viva_are_passed(client, database, kwargs, action):
    seed(database, **kwargs)
    response = call(client, action)
    assert response.status_code == 409 and "both the project score and the viva" in response.json()["detail"]


def test_unknown_or_missing_submission(client, database):
    assert client.post("/api/invoke", json={"action": "preview_certificate", "payload": {"submission_id": "nope"}}).status_code == 404
    assert client.post("/api/invoke", json={"action": "preview_certificate", "payload": {}}).status_code == 400


def test_the_preview_starts_with_the_students_name_and_is_editable(client, database):
    seed(database)
    body = call(client, "preview_certificate").json()
    assert body["name"] == "Learner" and body["editable"] is True and body["confirmed"] is False
    assert body["project_title"] == "Static Login Page" and body["certificate_id"].startswith("DDT-CAP-")
    assert body["content_type"] == "image/jpeg" and base64.b64decode(body["preview"])[:2] == b"\xff\xd8"


def test_a_preview_with_an_edited_name_shows_it_but_stores_nothing(client, database):
    seed(database)
    assert call(client, "preview_certificate", name="  Asha  Rao ").json()["name"] == "Asha Rao"
    with database() as session:
        assert session.get(Submission, "sub1").certificate_json is None


def test_an_invalid_name_is_a_422_with_the_reason(client, database):
    seed(database)
    for action in ("preview_certificate", "confirm_certificate"):
        response = call(client, action, name="Asha<script>")
        assert response.status_code == 422 and "letters" in response.json()["detail"]
    with database() as session:
        assert session.get(Submission, "sub1").certificate_json is None


def test_cannot_download_before_confirming(client, database):
    seed(database)
    response = call(client, "download_certificate")
    assert response.status_code == 409 and "Confirm the certificate" in response.json()["detail"]
    assert client.get("/api/submission/sub1/certificate.pdf").status_code == 409


def test_ok_locks_the_name_and_the_certificate_downloads(client, database):
    seed(database)
    confirmed = call(client, "confirm_certificate", name="Asha Rao").json()
    assert confirmed["confirmed"] is True and confirmed["editable"] is False and confirmed["name"] == "Asha Rao"
    with database() as session:
        record = session.get(Submission, "sub1").certificate_json
        assert record["confirmed"] is True and record["name"] == "Asha Rao" and record["certificate_id"].startswith("DDT-CAP-")

    body = call(client, "download_certificate").json()
    pdf = base64.b64decode(body["data"])
    assert body["content_type"] == "application/pdf" and body["filename"] == "Certificate_Asha-Rao_Static-Login-Page.pdf"
    for text in (b"ASHA RAO", b"STATIC LOGIN PAGE", b"Technology: HTML/CSS/JS", b"Form validation", b"PROJECT: GOOD", b"VIVA VOCE: GOOD"):
        assert text in pdf, text

    direct = client.get("/api/submission/sub1/certificate.pdf")
    assert direct.status_code == 200 and direct.headers["content-type"] == "application/pdf"
    assert direct.headers["content-disposition"] == 'attachment; filename="Certificate_Asha-Rao_Static-Login-Page.pdf"'


def test_a_confirmed_certificate_can_no_longer_be_edited(client, database):
    seed(database)
    call(client, "confirm_certificate", name="Asha Rao")
    again = call(client, "confirm_certificate", name="Someone Else").json()
    assert again["name"] == "Asha Rao"                                          # OK twice does not rename it
    preview = call(client, "preview_certificate", name="Someone Else").json()
    assert preview["name"] == "Asha Rao" and preview["editable"] is False and preview["confirmed"] is True
    assert b"ASHA RAO" in base64.b64decode(call(client, "download_certificate").json()["data"])


def test_confirming_without_a_name_uses_the_students_own(client, database):
    seed(database)
    assert call(client, "confirm_certificate").json()["name"] == "Learner"


def test_the_issue_date_and_id_do_not_change_between_downloads(client, database):
    seed(database)
    call(client, "confirm_certificate", name="Asha Rao")
    first = base64.b64decode(call(client, "download_certificate").json()["data"])
    second = base64.b64decode(call(client, "download_certificate").json()["data"])
    pick = lambda pdf: (re.search(rb"Date of Issue:  [^\n]+", printed(pdf)).group(), re.search(rb"DDT-CAP-\d{4}-[0-9A-Z]{4,8}", printed(pdf)).group())
    assert pick(first) == pick(second)
