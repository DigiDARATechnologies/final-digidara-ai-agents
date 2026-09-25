from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock

import pytest
from app import config, viva
from app.api import routes
from app.db.models import AssignmentStatus, ProjectAssignment, Submission, SubmissionStatus
from app.graph import nodes
from app.llm.client import LLMError


def upload(client, report="report.docx", source="source.zip", data=b"fixture"):
    # File-content parsing is tested by the real submission graph below;
    # these API tests isolate upload validation and state persistence.
    return client.post("/api/submission/upload", data={"thread_id": "thread"}, files={"docx_file": (report, data), "zip_file": (source, data)})

def answer(client, submission_id, index, text="Explanation"):
    return client.post("/api/invoke", json={"action": "submit_viva_answer", "payload": {"submission_id": submission_id, "question_id": index, "answer": text}})

@pytest.mark.parametrize("report,source,data,status", [("report.pdf", "source.zip", b"x", 400), ("report.docx", "source.txt", b"x", 400), ("report.docx", "source.zip", b"", 400), ("report.docx", "source.zip", b"123456", 413)])
def test_invalid_uploads_leave_no_submission(client, workflow, database, monkeypatch, report, source, data, status):
    monkeypatch.setattr(config, "MAX_UPLOAD_BYTES", 5)
    assert upload(client, report, source, data).status_code == status
    with database() as session:
        assert session.query(Submission).count() == 0
    assert not list(config.UPLOAD_DIR.iterdir())

@pytest.mark.parametrize("condition,status", [("graded", 409), ("expired", 410), ("missing", 404)])
def test_submission_guards(client, workflow, state, database, condition, status):
    if condition == "graded": state["status"] = "graded"
    with database() as session:
        assignment = session.get(ProjectAssignment, "assignment")
        if condition == "expired": assignment.deadline_at = datetime.now(timezone.utc) - timedelta(days=1)
        if condition == "missing": session.delete(assignment)
        session.commit()
    assert upload(client).status_code == status
    with database() as session:
        assert session.query(Submission).count() == 0

def test_upload_rejected_while_a_previous_submission_is_still_processing(client, workflow, database):
    with database() as session:
        session.add(Submission(id="in-flight", assignment_id="assignment", docx_path="x", zip_path="y", status=SubmissionStatus.processing))
        session.commit()
    response = upload(client)
    assert response.status_code == 409
    with database() as session:
        # Only the pre-existing in-flight row -- no second Submission was created.
        assert session.query(Submission).count() == 1

def test_a_failed_submission_run_is_marked_error_not_left_stuck_processing(client, workflow, database, monkeypatch):
    from fastapi import HTTPException
    monkeypatch.setattr(routes, "_run_submission", Mock(side_effect=HTTPException(502, "AI service unavailable")))

    first = upload(client)
    assert first.status_code == 502
    with database() as session:
        rows = session.query(Submission).all()
        assert len(rows) == 1
        assert rows[0].status == SubmissionStatus.error

    # The failed attempt must not permanently block a real retry.
    monkeypatch.setattr(routes, "_run_submission", lambda value: {"status": "graded", "passed": True, "final_score": 85, "feedback": "Good work"})
    second = upload(client)
    assert second.status_code == 200

def test_passing_submission_persists_files_and_hides_score_until_viva(client, workflow, database):
    response = upload(client)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "pending_viva"
    assert body["final_score"] is None
    assert body["viva_question"] == {"id": 0, "question": "Explain concept 0"}
    with database() as session:
        row = session.get(Submission, body["submission_id"])
        assert row.status == SubmissionStatus.pending_viva
        assert row.score_json["final_score"] == 85
        assert Path(row.docx_path).read_bytes() == b"fixture"
        assert Path(row.zip_path).read_bytes() == b"fixture"
        assert row.viva_answers_json == []
    assert workflow.update_state.call_args.args[1] == {"status": "pending_viva"}

@pytest.mark.parametrize("result,status", [({"status": "error", "feedback": "Invalid document"}, 422), ({"status": "needs_revision", "revision_notes": "Add tests", "passed": False, "final_score": 40}, 200)])
def test_failed_evaluation_does_not_start_viva(client, workflow, monkeypatch, result, status):
    monkeypatch.setattr(routes, "_run_submission", lambda state: result)
    viva_generator = Mock(side_effect=AssertionError("Viva must not run"))
    monkeypatch.setattr(routes, "generate_viva_questions", viva_generator)
    response = upload(client)
    assert response.status_code == status
    if status == 200:
        assert response.json()["revision_notes"] == "Add tests"
        assert response.json()["passed"] is False
    else: assert response.json()["detail"] == "Invalid document"
    assert workflow.update_state.call_args.args[1]["status"] == result["status"]
    viva_generator.assert_not_called()

def finish_attempt(client, submission_id, monkeypatch, correct_count, total=10):
    """Answer every question of the current attempt; `correct_count` of them are judged correct."""
    verdict = Mock(side_effect=[{"correct": i < correct_count, "note": "Reviewed"} for i in range(total)])
    monkeypatch.setattr(routes, "verify_viva_answer", verdict)
    last = None
    for index in range(total):
        response = answer(client, submission_id, index)
        assert response.status_code == 200
        last = response.json()
    return last


def start_attempt(client, submission_id):
    return client.post("/api/invoke", json={"action": "start_viva_attempt", "payload": {"submission_id": submission_id}})


@pytest.mark.parametrize("correct_count,rating", [(5, "Average"), (7, "Average"), (8, "Good"), (10, "Good")])
def test_viva_pass_mark_is_fifty_percent_and_the_result_is_a_rating_not_a_mark(client, workflow, database, monkeypatch, correct_count, rating):
    submission_id = upload(client).json()["submission_id"]
    assert answer(client, submission_id, 1).status_code == 409
    result = finish_attempt(client, submission_id, monkeypatch, correct_count)
    assert result["passed"] is True and result["status"] == "graded"
    assert result["viva_rating"] == rating and result["final_score"] == 85
    assert "Viva result: " + rating in result["feedback"] and " of 10" not in result["feedback"]
    with database() as session:
        row = session.get(Submission, submission_id)
        assert row.viva_passed is True and row.status == SubmissionStatus.graded
        assert [a["rating"] for a in row.viva_attempts_json] == [rating]
    assert answer(client, submission_id, 0).status_code == 409


def test_a_failed_attempt_can_be_retaken_with_new_questions_up_to_three_times(client, workflow, database, monkeypatch):
    seen_avoid = []

    def fresh_questions(topic, medium, code_files, avoid=None):
        seen_avoid.append(list(avoid or []))
        round_number = len(seen_avoid)
        return [{"id": i, "question": f"Round {round_number} question {i}", "expected_concepts": ["c"]} for i in range(10)]

    submission_id = upload(client).json()["submission_id"]
    monkeypatch.setattr(routes, "generate_viva_questions", fresh_questions)

    first = finish_attempt(client, submission_id, monkeypatch, 4)          # 40% -> not passed, 2 attempts left
    assert first["status"] == "viva_retry" and first["viva_rating"] == "Bad"
    assert first["viva_attempt"] == 1 and first["viva_attempts_left"] == 2 and first["viva_attempts_total"] == 3
    assert first["passed"] is None and first["final_score"] is None       # nothing is revealed yet
    assert answer(client, submission_id, 0).status_code == 409             # must start the next attempt first

    second_start = start_attempt(client, submission_id).json()
    assert second_start["status"] == "pending_viva" and second_start["viva_attempt"] == 2
    assert second_start["viva_question"]["question"] == "Round 1 question 0"
    assert any("Explain concept" in q for q in seen_avoid[0])              # attempt 1's questions are passed as "already asked"
    assert start_attempt(client, submission_id).status_code == 409         # attempt 2 is under way

    second = finish_attempt(client, submission_id, monkeypatch, 3)
    assert second["status"] == "viva_retry" and second["viva_attempts_left"] == 1
    third_start = start_attempt(client, submission_id).json()
    assert third_start["viva_attempt"] == 3 and third_start["viva_attempts_left"] == 0
    assert any("Round 1 question" in q for q in seen_avoid[1]) and any("Explain concept" in q for q in seen_avoid[1])

    third = finish_attempt(client, submission_id, monkeypatch, 2)          # out of attempts
    assert third["status"] == "needs_revision" and third["passed"] is False and third["viva_rating"] == "Bad"
    assert "not passed after 3 attempts" in third["feedback"]
    assert start_attempt(client, submission_id).status_code == 409
    with database() as session:
        row = session.get(Submission, submission_id)
        assert row.viva_passed is False and len(row.viva_attempts_json) == 3


def test_passing_on_a_later_attempt_grades_the_project(client, workflow, database, monkeypatch):
    submission_id = upload(client).json()["submission_id"]
    assert finish_attempt(client, submission_id, monkeypatch, 3)["status"] == "viva_retry"
    assert start_attempt(client, submission_id).status_code == 200
    result = finish_attempt(client, submission_id, monkeypatch, 9)
    assert result["status"] == "graded" and result["passed"] is True and result["viva_rating"] == "Good"
    with database() as session:
        row = session.get(Submission, submission_id)
        assert row.status == SubmissionStatus.graded and row.viva_passed is True
        assert [a["passed"] for a in row.viva_attempts_json] == [False, True]


def test_start_viva_attempt_guards(client, workflow, monkeypatch):
    assert start_attempt(client, "missing").status_code == 404
    submission_id = upload(client).json()["submission_id"]
    assert start_attempt(client, submission_id).status_code == 409         # nothing finished yet
    assert client.post("/api/invoke", json={"action": "start_viva_attempt", "payload": {}}).status_code == 400


def test_viva_progress_is_reported_one_question_at_a_time_and_replays_are_rejected(client, workflow, monkeypatch):
    submission_id = upload(client).json()["submission_id"]
    verdict = Mock(return_value={"correct": True, "note": "ok"})
    monkeypatch.setattr(routes, "verify_viva_answer", verdict)
    assert answer(client, submission_id, 1).status_code == 409
    verdict.assert_not_called()
    for index in range(9):
        result = answer(client, submission_id, index).json()
        assert result["status"] == "pending_viva" and result["final_score"] is None
        assert result["viva_question"]["id"] == index + 1 and result["viva_attempt"] == 1
        assert answer(client, submission_id, index).status_code == 409
    assert verdict.call_count == 9


def test_unknown_submission(client):
    assert answer(client, "missing", 0).status_code == 404

def test_unknown_topic_rejected_without_advancing_graph(client, workflow, state, monkeypatch):
    state["topic_options"] = [{"id": "one", "title": "Task tracker"}]
    advance = Mock()
    monkeypatch.setattr(routes, "_invoke_graph", advance)
    assert client.post("/api/topic/choose", json={"thread_id": "thread", "topic_id": "other"}).status_code == 400
    advance.assert_not_called()

def test_topic_selection_preserves_generated_option(client, workflow, state, monkeypatch):
    topic = state["chosen_topic"]
    state["topic_options"] = [topic]
    advance = Mock(return_value={"chosen_topic": topic, "requirements": {"features": ["Save tasks"]}})
    monkeypatch.setattr(routes, "_invoke_graph", advance)
    response = client.post("/api/topic/choose", json={"thread_id": "thread", "topic_id": "one"})
    assert response.status_code == 200
    assert response.json()["requirements"] == {"features": ["Save tasks"]}
    advance.assert_called_once_with({"chosen_topic": topic}, "thread")

def test_topic_generation_includes_prior_titles(state, database, monkeypatch):
    with database() as session:
        session.get(ProjectAssignment, "assignment").topic_json = {"title": "Previous project"}
        session.commit()
    provider = Mock(return_value={"options": [{"id": "new", "title": "New project"}]})
    monkeypatch.setattr(nodes, "call_json", provider)
    assert nodes.topic_generator_node(state)["topic_options"][0]["id"] == "new"
    assert "Previous project" in provider.call_args.kwargs["system"]

def test_generation_provider_failure_is_not_a_success(state, monkeypatch):
    monkeypatch.setattr(nodes, "call_json", Mock(side_effect=LLMError("offline")))
    with pytest.raises(LLMError): nodes.topic_generator_node(state)

def test_timer_persists_topic_and_submission_window(state, database):
    before = datetime.now(timezone.utc)
    result = nodes.timer_init_node(state)
    deadline = datetime.fromisoformat(result["deadline_at"])
    assert before + timedelta(days=config.SUBMISSION_WINDOW_DAYS) <= deadline <= datetime.now(timezone.utc) + timedelta(days=config.SUBMISSION_WINDOW_DAYS)
    with database() as session:
        assignment = session.get(ProjectAssignment, "assignment")
        assert assignment.status == AssignmentStatus.in_progress
        assert assignment.topic_json == state["chosen_topic"]
        assert assignment.deadline_at is not None

@pytest.mark.parametrize("passed", [True, False])
def test_evaluation_feedback_persists_grade_and_allows_revision(state, database, monkeypatch, passed):
    with database() as session:
        session.add(Submission(id="submission", assignment_id="assignment", docx_path="report.docx", zip_path="source.zip"))
        session.commit()
    monkeypatch.setattr(nodes, "call_text", lambda **kwargs: "Evaluation feedback")
    result = nodes.feedback_generator_node({**state, "submission_id": "submission", "passed": passed, "final_score": 80 if passed else 40})
    expected = "graded" if passed else "needs_revision"
    assert result["status"] == expected
    with database() as session:
        assert session.get(Submission, "submission").status.value == expected
        assert session.get(ProjectAssignment, "assignment").status.value == expected
        assert session.get(Submission, "submission").score_json["passed"] is passed

def test_viva_question_limit_and_numbering(monkeypatch):
    monkeypatch.setattr(viva, "call_json", lambda **kwargs: {"questions": [{"id": 90, "question": f"Explain {i}", "expected_concepts": ["concept"]} for i in range(12)]})
    questions = viva.generate_viva_questions({"title": "Task tracker"}, "local", {})
    assert [q["id"] for q in questions] == list(range(10))
    assert questions[0]["expected_concepts"] == ["concept"]


def test_a_retake_never_repeats_an_earlier_question_even_if_the_model_does(monkeypatch):
    earlier = ["What does the login function return?", "Why is a list used here?"]
    calls = []

    def model(**kwargs):
        calls.append(kwargs["system"])
        if len(calls) == 1:   # repeats both earlier questions (differently punctuated) plus 8 new ones
            texts = ["what does the LOGIN function return", "Why is a list used here"] + [f"New question {i}" for i in range(8)]
        else:
            texts = ["Top-up question A", "Top-up question B", "New question 0"]
        return {"questions": [{"question": t, "expected_concepts": ["c"]} for t in texts]}

    monkeypatch.setattr(viva, "call_json", model)
    questions = viva.generate_viva_questions({"title": "T"}, "local", {}, earlier)
    texts = [q["question"] for q in questions]
    assert len(texts) == 10 and len(set(texts)) == 10
    assert not any(viva._fingerprint(t) in {viva._fingerprint(e) for e in earlier} for t in texts)
    assert "RE-ATTEMPT" in calls[0] and "What does the login function return?" in calls[0]


@pytest.mark.parametrize("correct,total,rating,passed", [(10, 10, "Good", True), (8, 10, "Good", True), (7, 10, "Average", True),
                                                          (5, 10, "Average", True), (4, 10, "Bad", False), (0, 10, "Bad", False), (0, 0, "Bad", False)])
def test_viva_rating_and_pass_mark(correct, total, rating, passed):
    assert viva.viva_rating(correct, total) == rating and viva.viva_passed(correct, total) is passed


def test_real_main_graph_pauses_for_topic_and_timer(state, monkeypatch, database):
    import uuid
    from app.graph.graph import compiled_graph
    topic = state["chosen_topic"]
    provider = Mock(side_effect=[{"options": [topic]}, {"features": ["Save tasks"]}, {"sections": ["Introduction"]}])
    monkeypatch.setattr(nodes, "call_json", provider)
    thread = {"configurable": {"thread_id": uuid.uuid4().hex}}
    # No certificate/enrollment gate -- every request starts straight at
    # topic generation.
    first = compiled_graph.invoke(state, thread)
    assert first["topic_options"] == [topic]
    assert compiled_graph.get_state(thread).next == ("requirement_expansion",)
    compiled_graph.update_state(thread, {"chosen_topic": topic})
    second = compiled_graph.invoke(None, thread)
    assert second["requirements"] == {"features": ["Save tasks"]}
    with database() as session:
        # Persisted so the Q&A agent can answer a requirements doubt before
        # the timer is confirmed (and about_markdown exists) -- not just
        # kept in the LangGraph checkpoint.
        assert session.get(ProjectAssignment, "assignment").requirements_json == {"features": ["Save tasks"]}
    assert compiled_graph.get_state(thread).next == ("timer_init",)
    final = compiled_graph.invoke(None, thread)
    assert final["deadline_at"]
    guide = final["submission_guide"]
    assert guide["sections"] == ["Introduction"]  # what the model wrote is kept...
    # ...but what the report needs is decided by code: three sections, no screenshots.
    assert guide["docx_required_sections"] == ["Problem Statement", "Approach", "Conclusion"]
    assert guide["required_screenshots"] == []
    assert compiled_graph.get_state(thread).next == ()
    assert provider.call_count == 3

@pytest.mark.parametrize("failure", ["docx", "zip"])
def test_real_submission_graph_stops_before_ai_on_invalid_files(state, tmp_path, monkeypatch, failure):
    from docx import Document
    from app.graph.graph import submission_graph
    report, archive = tmp_path / "report.docx", tmp_path / "source.zip"
    if failure == "docx": report.write_bytes(b"not a document")
    else: Document().save(report)
    archive.write_bytes(b"not a zip")
    provider = Mock(side_effect=AssertionError("Invalid files must not reach AI grading"))
    monkeypatch.setattr(nodes, "call_json", provider)
    result = submission_graph.invoke({**state, "docx_path": str(report), "zip_path": str(archive)})
    assert result["status"] == "error"
    assert (".docx" if failure == "docx" else ".zip") in result["feedback"]
    provider.assert_not_called()

@pytest.mark.parametrize("complete,zip_complete,expected", [(True, False, True), (False, True, False)])
def test_structure_gate_uses_report_completeness(complete, zip_complete, expected):
    assert nodes.structure_gate_passed({"structure_score": {"is_complete": complete}, "zip_structure_score": {"is_complete": zip_complete}}) is expected


# --- syntax errors: sent back before any scoring, with structured details -----

def _report_docx(path):
    from docx import Document
    document = Document()
    for heading in ("Problem Statement", "Approach", "Conclusion"):
        document.add_heading(heading, level=1)
        document.add_paragraph(f"A substantive explanation for the {heading} section of this project report.")
    document.save(path)


def _zip_with(path, files):
    import zipfile
    with zipfile.ZipFile(path, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)


def test_real_submission_graph_sends_syntax_errors_back_before_any_scoring(state, database, tmp_path, monkeypatch):
    from app.graph.graph import submission_graph
    report, archive = tmp_path / "report.docx", tmp_path / "source.zip"
    _report_docx(report)
    _zip_with(archive, {
        "Tracker/src/main.py": "def total(items):\n    return sum(items\n",
        "Tracker/src/util.py": "def fine():\n    return 1\n",
    })
    systems = []

    def provider(**kwargs):
        systems.append(kwargs["system"])
        return {"is_complete": True, "weak_sections": [], "structure_quality": "good", "clutter_flags": [], "notes": ""}

    monkeypatch.setattr(nodes, "call_json", provider)
    monkeypatch.setattr(nodes, "call_text", Mock(side_effect=AssertionError("must not write final feedback")))
    guide = {"docx_required_sections": ["Problem Statement", "Approach", "Code", "Output Screenshots", "Conclusion"],
             "required_paths": [{"path": "Tracker/src", "type": "dir"}]}
    result = submission_graph.invoke({**state, "submission_id": "s1", "submission_guide": guide,
                                      "docx_path": str(report), "zip_path": str(archive)})

    assert result["status"] == "needs_revision"
    assert result["syntax_report"]["error_count"] == 1
    error = result["syntax_report"]["errors"][0]
    assert error["path"] == "Tracker/src/main.py" and error["language"] == "Python"
    assert error["line"] and error["source_line"] and error["message"]
    assert result["revision_notes"] == ""                      # nothing else was wrong
    assert "final_score" not in result and "code_quality_score" not in result
    # Only the two structure reviewers ran; no scoring model and no sandbox run.
    assert not any("Code Quality Reviewer" in system or "Requirements Verifier" in system for system in systems)
    assert "execution_result" not in result


def test_real_submission_graph_scores_a_clean_submission(state, database, tmp_path, monkeypatch):
    from app.graph.graph import submission_graph
    report, archive = tmp_path / "report.docx", tmp_path / "source.zip"
    _report_docx(report)
    _zip_with(archive, {"Tracker/src/main.py": "def total(items):\n    return sum(items)\n"})

    def provider(**kwargs):
        system = kwargs["system"]
        if "Code Quality Reviewer" in system:
            return {"structure_score": 20, "syntax_score": 25, "maintainability_score": 20, "completeness_score": 20, "total_code_score": 85}
        if "Requirements Verifier" in system:
            return {"output_correct": True, "requirements_check": [{"requirement": "Add up items", "status": "met", "evidence": "main.total"}]}
        if "Final Score Decision" in system:
            return {"final_score": 85, "reasoning": "solid"}
        return {"is_complete": True, "weak_sections": [], "structure_quality": "good", "clutter_flags": [], "notes": ""}

    monkeypatch.setattr(nodes, "call_json", provider)
    monkeypatch.setattr(nodes, "call_text", lambda **kwargs: "Well done.")
    monkeypatch.setattr(nodes, "run_python_submission", Mock(side_effect=nodes.Judge0Unavailable("offline")))
    result = submission_graph.invoke({**state, "submission_id": "s2", "docx_path": str(report), "zip_path": str(archive),
                                      "requirements": {"functional_requirements": ["Add up items"]},
                                      "submission_guide": {"docx_required_sections": ["Problem Statement", "Approach", "Conclusion"]}})
    assert result["syntax_report"]["has_errors"] is False
    assert result["output_verification"]["requirements_check"][0]["status"] == "met"
    assert result["final_score"] == 85 and result["passed"] is True


def test_upload_response_carries_the_structured_syntax_errors(client, workflow, monkeypatch):
    errors = [{"path": "P/src/main.py", "language": "Python", "line": 2, "column": 12,
               "message": "'(' was never closed", "source_line": "    return sum(items"}]
    monkeypatch.setattr(routes, "_run_submission", lambda value: {
        "status": "needs_revision", "revision_notes": "", "syntax_report": {"errors": errors, "has_errors": True}})
    response = upload(client)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "needs_revision"
    assert body["syntax_errors"] == errors
    assert not body["revision_notes"]


def test_upload_response_has_no_syntax_errors_field_content_when_the_code_parses(client, workflow, monkeypatch):
    monkeypatch.setattr(routes, "_run_submission", lambda value: {
        "status": "needs_revision", "revision_notes": "Report: add more detail.", "syntax_report": {"errors": [], "has_errors": False}})
    body = upload(client).json()
    assert body["syntax_errors"] is None and body["revision_notes"] == "Report: add more detail."
