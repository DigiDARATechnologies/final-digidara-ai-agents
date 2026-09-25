"""The final project report PDF: available only after BOTH the score and the viva pass."""
import base64
import re
from datetime import datetime, timezone

import pytest
from app.db.models import ProjectAssignment, Student, Submission, SubmissionStatus
from app.graph import nodes
from app.reports.final_report import assemble_report_data, build_final_report_pdf, report_filename

SECRET_RUBRIC = "PRIVATE-RUBRIC-CONCEPT"


def sample_data(**overrides):
    data = {
        "report_id": "abc123", "student_name": "Prem Kumar", "project_title": "Static Login Page",
        "project_summary": "A responsive login page.", "objective": "Validate input in the browser.",
        "functional_requirements": ["Validate email"], "technical_constraints": ["Run offline"],
        "submitted_at": datetime(2026, 9, 25, 7, 12, tzinfo=timezone.utc), "deadline_at": datetime(2026, 10, 2, tzinfo=timezone.utc),
        "generated_at": datetime(2026, 9, 25, 9, 0, tzinfo=timezone.utc),
        "final_score": 86.5, "pass_mark": 70, "passed": True,
        "viva_score": 8, "viva_total": 10, "viva_pass_mark": 5, "viva_passed": True, "viva_pass_percent": 50,
        "viva_rating": "Good", "viva_attempts": [{"attempt": 1, "rating": "Bad", "passed": False}, {"attempt": 2, "rating": "Good", "passed": True}],
        "code_quality": {"structure_score": 21, "syntax_score": 23, "maintainability_score": 20, "completeness_score": 22,
                         "total_code_score": 86, "strengths": ["Clean modules"], "weaknesses": ["No tests"]},
        "requirements_check": [{"requirement": "Validate email", "status": "met", "evidence": "validate.js: isValidEmail()"}],
        "constraints_check": [], "screenshots_check": [{"screenshot": "01-form.png", "status": "present", "evidence": "OCR ok"}],
        "screenshot_files": ["P/output_screenshots/01-form.png"], "syntax": {"checked": 2, "languages": ["Python"], "errors": 0},
        "report_sections": ["Problem Statement", "Approach", "Conclusion"], "submitted_files": ["P/src/main.py"],
        "feedback": "### Overall\nWell done.\n- Clean code", "score_reasoning": "Solid.",
        "viva": [{"number": i, "question": f"Question {i}?", "answer": "An answer.", "correct": i != 3, "note": "ok"} for i in range(1, 11)],
    }
    data.update(overrides)
    return data


def pages_and_logo_draws(pdf):
    return len(re.findall(rb"/Type /Page\b(?!s)", pdf)), re.findall(rb"/(FormXob\.[0-9a-f]+) Do", pdf)


def test_the_report_is_a_pdf_with_the_result_the_student_and_the_project():
    pdf = build_final_report_pdf(sample_data())
    assert pdf.startswith(b"%PDF-")
    for text in (b"Prem Kumar", b"Static Login Page", b"PASSED", b"86.5 / 100", b"GOOD", b"Capstone Project Completion Report"):
        assert text in pdf, text


def test_the_viva_is_shown_as_a_rating_per_attempt_and_never_as_a_mark():
    pdf = build_final_report_pdf(sample_data())
    assert b"8 / 10" not in pdf and b"8 of 10" not in pdf
    for text in (b"Attempt", b"Not passed", b"Passed", b"at least 50% correct", b"Bad", b"Good"):
        assert text in pdf, text


def test_the_logo_is_on_every_page_and_pages_are_numbered_x_of_y():
    pdf = build_final_report_pdf(sample_data(
        viva=[{"number": i, "question": "Why " * 40, "answer": "Because " * 60, "correct": True, "note": "n"} for i in range(1, 11)]))
    pages, draws = pages_and_logo_draws(pdf)
    assert pages >= 3
    assert len(draws) == pages and len(set(draws)) == 1                 # the same logo, once per page
    for number in range(1, pages + 1):
        assert f"Page {number} of {pages}".encode() in pdf


def test_the_report_covers_every_section():
    pdf = build_final_report_pdf(sample_data())
    for heading in (b"1. Project overview", b"2. Requirements", b"3. Code quality", b"4. Automated checks", b"5. Viva", b"6. Reviewer feedback"):
        assert heading in pdf, heading


def test_the_viva_table_shows_each_answer_result_but_never_the_private_rubric():
    pdf = build_final_report_pdf(sample_data())
    assert pdf.count(b"Not correct") == 1 and pdf.count(b"Correct") >= 9
    assert SECRET_RUBRIC.encode() not in pdf


def test_student_text_cannot_break_the_layout_or_inject_markup():
    nasty = "<b>bold</b> & <para>oops</para> 日本語 😀 “quotes” — dash"
    pdf = build_final_report_pdf(sample_data(student_name=nasty, feedback=nasty, viva=[
        {"number": 1, "question": nasty, "answer": nasty, "correct": True, "note": nasty}]))
    # Unescaped, that text is a markup parse error in reportlab: building at all proves it was escaped,
    # and the words survive rather than being swallowed as tags.
    assert pdf.startswith(b"%PDF-")
    assert b"oops" in pdf and b"quotes" in pdf and b"bold" in pdf


def test_an_old_submission_with_missing_pieces_still_produces_a_report():
    minimal = {"report_id": "x", "student_name": "", "project_title": "", "project_summary": "", "objective": "",
               "functional_requirements": [], "technical_constraints": [], "submitted_at": None, "deadline_at": None,
               "generated_at": datetime.now(timezone.utc), "final_score": None, "pass_mark": 70, "passed": True,
               "viva_score": None, "viva_total": 10, "viva_pass_mark": 6, "viva_passed": True, "code_quality": {},
               "requirements_check": [], "constraints_check": [], "screenshots_check": [], "screenshot_files": [],
               "syntax": {"checked": 0, "languages": [], "errors": 0}, "report_sections": [], "submitted_files": [],
               "feedback": "", "score_reasoning": "", "viva": []}
    pdf = build_final_report_pdf(minimal)
    assert pdf.startswith(b"%PDF-") and b"Viva result not recorded" in pdf and b"No written feedback was recorded" in pdf


def test_the_file_name_is_safe_and_descriptive():
    assert report_filename("Static Login Page / with <Validation>") == "Capstone_Report_Static-Login-Page-with-Validation.pdf"
    assert report_filename("") == "Capstone_Report_Project.pdf"


# ------------------------------------------------------------ from the database

def seed(database, *, status=SubmissionStatus.graded, passed=True, viva_passed=True):
    with database() as session:
        assignment = session.get(ProjectAssignment, "assignment")
        assignment.topic_json = {"id": "one", "title": "Static Login Page", "summary": "A responsive login page."}
        assignment.requirements_json = {"objective": "Validate input.", "functional_requirements": ["Validate email"],
                                        "technical_constraints": ["Run offline"]}
        session.add(Submission(
            id="sub1", assignment_id="assignment", docx_path="d", zip_path="z", status=status,
            score_json={"final_score": 88, "passed": passed, "feedback": "Great.", "score_reasoning": "Solid.",
                        "code_quality_score": {"total_code_score": 88, "strengths": ["s"], "weaknesses": ["w"]},
                        "output_verification": {"requirements_check": [{"requirement": "Validate email", "status": "met", "evidence": "x"}]},
                        "syntax_report": {"checked_files": ["a.py"], "checked_languages": ["Python"], "error_count": 0},
                        "screenshot_evidence": {"valid_files": ["P/output_screenshots/1.png"]},
                        "structure_score": {"matched_sections": ["Problem Statement", "Approach", "Conclusion"]},
                        "submitted_files": ["P/src/a.py"]},
            feedback_text="Great work.",
            viva_questions_json=[{"id": 0, "question": "Why?", "expected_concepts": [SECRET_RUBRIC]},
                                 {"id": 1, "question": "How?", "expected_concepts": [SECRET_RUBRIC]}],
            viva_answers_json=[{"question_id": 0, "answer": "Because.", "correct": True, "note": "good"},
                               {"question_id": 1, "answer": "Not sure", "correct": False, "note": "vague"}],
            viva_score=8, viva_passed=viva_passed,
            viva_attempts_json=[{"attempt": 1, "correct": 8, "total": 10, "rating": "Good", "passed": True, "questions": [], "answers": []}],
        ))
        session.commit()


def test_report_data_is_assembled_from_the_stored_rows(database):
    seed(database)
    with database() as session:
        submission = session.get(Submission, "sub1")
        assignment = session.get(ProjectAssignment, "assignment")
        data = assemble_report_data(assignment, session.get(Student, "student"), submission, 70, 5)
    assert data["student_name"] == "Learner" and data["project_title"] == "Static Login Page"
    assert data["final_score"] == 88 and data["passed"] and data["viva_passed"] and data["viva_score"] == 8
    assert data["requirements_check"][0]["status"] == "met" and data["report_sections"] == ["Problem Statement", "Approach", "Conclusion"]
    assert data["viva_rating"] == "Good" and data["viva_attempts"] == [{"attempt": 1, "rating": "Good", "passed": True}]
    assert [item["correct"] for item in data["viva"]] == [True, False]
    assert data["viva"][1]["answer"] == "Not sure"
    assert SECRET_RUBRIC not in repr(data)                    # the private rubric never reaches the report


@pytest.mark.parametrize("kwargs", [
    {"status": SubmissionStatus.needs_revision},   # failed grade
    {"status": SubmissionStatus.pending_viva},     # viva not finished
    {"passed": False},                              # score below the pass mark
    {"viva_passed": False},                         # viva failed
])
def test_no_report_until_both_the_score_and_the_viva_are_passed(client, database, kwargs):
    seed(database, **kwargs)
    response = client.get("/api/submission/sub1/final-report.pdf")
    assert response.status_code == 409
    assert "both the project score and the viva" in response.json()["detail"]


def test_unknown_submission_is_a_404(client, database):
    assert client.get("/api/submission/nope/final-report.pdf").status_code == 404


def test_the_report_downloads_once_both_are_passed(client, database):
    seed(database)
    response = client.get("/api/submission/sub1/final-report.pdf")
    assert response.status_code == 200 and response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"] == 'attachment; filename="Capstone_Report_Static-Login-Page.pdf"'
    assert response.content.startswith(b"%PDF-") and b"Learner" in response.content and b"PASSED" in response.content
    assert SECRET_RUBRIC.encode() not in response.content


def test_the_gateway_action_returns_the_same_pdf_as_base64(client, database):
    seed(database)
    body = client.post("/api/invoke", json={"action": "download_final_report", "payload": {"submission_id": "sub1"}}).json()
    assert body["content_type"] == "application/pdf" and body["filename"] == "Capstone_Report_Static-Login-Page.pdf"
    assert base64.b64decode(body["data"]).startswith(b"%PDF-")


def test_the_gateway_action_refuses_an_ineligible_or_missing_request(client, database):
    seed(database, viva_passed=False)
    assert client.post("/api/invoke", json={"action": "download_final_report", "payload": {"submission_id": "sub1"}}).status_code == 409
    assert client.post("/api/invoke", json={"action": "download_final_report", "payload": {}}).status_code == 400


def test_grading_stores_what_the_report_needs(database, monkeypatch):
    with database() as session:
        session.add(Submission(id="sub2", assignment_id="assignment", docx_path="d", zip_path="z", status=SubmissionStatus.processing))
        session.commit()
    monkeypatch.setattr(nodes, "call_text", lambda **kwargs: "Well done.")
    nodes.feedback_generator_node({
        "passed": True, "final_score": 90, "submission_id": "sub2", "assignment_id": "assignment", "student_name": "L",
        "chosen_topic": {"title": "T"}, "zip_file_tree": ["P/src/a.py", "P/output_screenshots/1.png"],
        "syntax_report": {"checked_files": ["P/src/a.py"], "checked_languages": ["Python"], "error_count": 0, "errors": [], "extra": 1},
        "screenshot_evidence": {"valid_files": ["P/output_screenshots/1.png"], "files": ["x"], "ocr_text": "long text"},
    })
    with database() as session:
        score = session.get(Submission, "sub2").score_json
    assert score["submitted_files"] == ["P/src/a.py", "P/output_screenshots/1.png"]
    assert score["screenshot_evidence"] == {"valid_files": ["P/output_screenshots/1.png"]}   # OCR text is not kept
    assert score["syntax_report"] == {"checked_files": ["P/src/a.py"], "checked_languages": ["Python"], "error_count": 0}
