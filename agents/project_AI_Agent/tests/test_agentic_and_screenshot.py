import inspect
from unittest.mock import Mock

import pytest

from app.agentic import qa_agent
from app.api import routes
from app.db.models import CourseMedium, ProjectAssignment, Submission, SubmissionStatus
from app.graph import nodes


# --- Fakes mimicking litellm's response shape for tool-calling completions ---

class _FakeFunction:
    def __init__(self, name, arguments):
        self.name = name
        self.arguments = arguments


class _FakeToolCall:
    def __init__(self, call_id, name, arguments):
        self.id = call_id
        self.function = _FakeFunction(name, arguments)

    def model_dump(self):
        return {"id": self.id, "type": "function", "function": {"name": self.function.name, "arguments": self.function.arguments}}


class _FakeMessage:
    def __init__(self, content=None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls


class _FakeResponse:
    def __init__(self, message, usage=None):
        self.choices = [type("Choice", (), {"message": message})()]
        self.usage = usage


# --- Phase 4: agentic Q&A loop ------------------------------------------------

def _seed_assignment(database, thread_id="qa-thread", assignment_id="qa-assignment"):
    with database() as session:
        session.add(ProjectAssignment(
            id=assignment_id, thread_id=thread_id, student_id="student", course_id="course",
            medium=CourseMedium.local, topic_json={"title": "Task Tracker"}, about_markdown="# About Task Tracker",
        ))
        session.commit()


def test_ask_project_question_calls_a_tool_then_answers(database, monkeypatch):
    _seed_assignment(database)
    responses = [
        _FakeResponse(_FakeMessage(content=None, tool_calls=[_FakeToolCall("call-1", "get_project_brief", "{}")])),
        _FakeResponse(_FakeMessage(content="Your project is Task Tracker.", tool_calls=None)),
    ]
    monkeypatch.setattr(qa_agent.litellm, "completion", Mock(side_effect=responses))
    monkeypatch.setattr(qa_agent, "record_usage", lambda *a, **k: None)

    result = qa_agent.ask_project_question("qa-thread", "What is my project about?")

    assert result["tools_used"] == ["get_project_brief"]
    assert "Task Tracker" in result["answer"]


def test_ask_project_question_answers_directly_without_tools(database, monkeypatch):
    _seed_assignment(database)
    monkeypatch.setattr(
        qa_agent.litellm, "completion",
        Mock(return_value=_FakeResponse(_FakeMessage(content="Sure, here's the answer.", tool_calls=None))),
    )
    monkeypatch.setattr(qa_agent, "record_usage", lambda *a, **k: None)

    result = qa_agent.ask_project_question("qa-thread", "Quick question")
    assert result["tools_used"] == []
    assert result["answer"] == "Sure, here's the answer."


def test_ask_project_question_bails_out_after_max_iterations(database, monkeypatch):
    _seed_assignment(database)
    always_tool_call = _FakeResponse(_FakeMessage(content=None, tool_calls=[_FakeToolCall("call-x", "get_project_brief", "{}")]))
    monkeypatch.setattr(qa_agent.litellm, "completion", Mock(return_value=always_tool_call))
    monkeypatch.setattr(qa_agent, "record_usage", lambda *a, **k: None)

    result = qa_agent.ask_project_question("qa-thread", "Loop forever?")
    assert len(result["tools_used"]) == qa_agent._MAX_TOOL_ITERATIONS
    assert "try rephrasing" in result["answer"]


def test_ask_project_question_unknown_thread_raises(database):
    with pytest.raises(qa_agent.ProjectNotFound):
        qa_agent.ask_project_question("does-not-exist", "Hello?")


def test_qa_ask_endpoint_rejects_pdf_attachment(client, database):
    # The `database` fixture already seeds a ProjectAssignment with
    # thread_id="thread" -- reused here since this request never reaches
    # ask_project_question (it's rejected for its attachment type first).
    response = client.post(
        "/api/qa/ask",
        data={"thread_id": "thread", "question": "What does this say?"},
        files={"attachment": ("notes.pdf", b"%PDF-1.4 fake", "application/pdf")},
    )
    assert response.status_code == 415


def test_qa_ask_endpoint_unknown_thread(client, monkeypatch):
    monkeypatch.setattr(routes, "ask_project_question", Mock(side_effect=qa_agent.ProjectNotFound("nope")))
    response = client.post("/api/qa/ask", data={"thread_id": "ghost", "question": "Hi"})
    assert response.status_code == 404


def test_invoke_ask_project_question_action(client, monkeypatch):
    """The frontend chat calls the JSON /api/invoke gateway contract, not the
    multipart /api/qa/ask route directly -- this is what capstoneFlow.ts uses
    to let a student ask a genuine question mid-viva instead of it being
    submitted as their literal viva answer."""
    monkeypatch.setattr(
        routes, "ask_project_question",
        Mock(return_value={"answer": "Your pie chart code is in chart.js.", "tools_used": ["read_submitted_file"]}),
    )
    response = client.post("/api/invoke", json={"action": "ask_project_question", "payload": {"thread_id": "thread", "question": "Where's my pie chart code?"}})
    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "Your pie chart code is in chart.js."
    assert body["tools_used"] == ["read_submitted_file"]


def test_invoke_ask_project_question_action_rejects_empty_question(client):
    response = client.post("/api/invoke", json={"action": "ask_project_question", "payload": {"thread_id": "thread", "question": "   "}})
    assert response.status_code == 400


# --- Phase 3: screenshot-based structure troubleshooting ---------------------

def test_structure_screenshot_endpoint_requires_missing_items(client, database):
    with database() as session:
        session.add(Submission(
            id="sub-clean", assignment_id="assignment", docx_path="x", zip_path="y",
            status=SubmissionStatus.needs_revision,
            zip_validation_json={"required_paths_detail": {"missing_items": [], "matched_items": []}},
        ))
        session.commit()
    response = client.post(
        "/api/submission/sub-clean/structure-screenshot",
        files={"image": ("shot.png", b"fake-png-bytes", "image/png")},
    )
    assert response.status_code == 400


def test_structure_screenshot_endpoint_analyzes_image(client, database, monkeypatch):
    with database() as session:
        session.add(Submission(
            id="sub-missing", assignment_id="assignment", docx_path="x", zip_path="y",
            status=SubmissionStatus.needs_revision,
            zip_validation_json={
                "required_paths_detail": {
                    "missing_items": [{"path": "TaskTracker/output_screenshots", "type": "dir", "description": "screenshots"}],
                    "matched_items": [{"path": "TaskTracker/src", "type": "dir", "description": "source"}],
                }
            },
        ))
        session.commit()

    monkeypatch.setattr(
        routes, "analyze_structure_screenshot",
        lambda image_bytes, mime_type, missing_items, matched_items: {
            "observations": [{"path": "TaskTracker/output_screenshots", "found_in_screenshot": False, "guidance": "Create it next to src/."}],
            "summary": "Add the output_screenshots folder.",
        },
    )
    response = client.post(
        "/api/submission/sub-missing/structure-screenshot",
        files={"image": ("shot.png", b"fake-png-bytes", "image/png")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["observations"][0]["path"] == "TaskTracker/output_screenshots"
    assert "Add the output_screenshots folder." in body["summary"]


def test_structure_screenshot_endpoint_rejects_non_image(client, database):
    with database() as session:
        session.add(Submission(
            id="sub-missing2", assignment_id="assignment", docx_path="x", zip_path="y",
            status=SubmissionStatus.needs_revision,
            zip_validation_json={"required_paths_detail": {"missing_items": [{"path": "a", "type": "dir", "description": ""}], "matched_items": []}},
        ))
        session.commit()
    response = client.post(
        "/api/submission/sub-missing2/structure-screenshot",
        files={"image": ("notes.txt", b"not an image", "text/plain")},
    )
    assert response.status_code == 400


def test_system_prompt_instructs_dispute_resolution_flow():
    """Regression guard for the requirement-dispute conversation flow: check
    the code first, only ask for a screenshot when code evidence alone is
    inconclusive and none was already attached, then give a clear verdict
    once one is available."""
    prompt = qa_agent._SYSTEM_PROMPT
    assert "HANDLING A DISPUTE" in prompt
    assert "read_submitted_file" in prompt
    assert "ask them to attach a" in prompt
    assert "screenshot" in prompt


def test_ask_project_question_dispute_uses_code_tool_then_answers(database, monkeypatch):
    """A student disputing a flagged-missing feature should get an answer
    that engaged with the actual code, not a canned response."""
    _seed_assignment(database)
    responses = [
        _FakeResponse(_FakeMessage(content=None, tool_calls=[_FakeToolCall("call-1", "list_submitted_files", "{}")])),
        _FakeResponse(_FakeMessage(content=None, tool_calls=[_FakeToolCall("call-2", "read_submitted_file", '{"path": "chart.js"}')])),
        _FakeResponse(_FakeMessage(content="Your chart.js does call Chart.js's pie() function, so the code is present.", tool_calls=None)),
    ]
    monkeypatch.setattr(qa_agent.litellm, "completion", Mock(side_effect=responses))
    monkeypatch.setattr(qa_agent, "record_usage", lambda *a, **k: None)

    result = qa_agent.ask_project_question("qa-thread", "You said my pie chart is missing but I wrote it — check chart.js")

    assert result["tools_used"] == ["list_submitted_files", "read_submitted_file"]
    assert "chart.js" in result["answer"]


# --- Phase 5: free/custom-topic submissions share the exact same checks ------

_SUBMISSION_PIPELINE_NODES = [
    nodes.docx_ingest_node, nodes.zip_ingest_node, nodes.structure_validation_node,
    nodes.zip_structure_validation_node, nodes.request_revision_node, nodes.code_execution_node,
    nodes.output_verification_node, nodes.code_quality_scorer_node, nodes.score_aggregator_node,
    nodes.feedback_generator_node,
]


def test_submission_pipeline_nodes_never_branch_on_free_topic_flag():
    """A free-topic ("custom project") request only changes topic GENERATION
    (see topic_generator_node/eligibility_check_node) -- every node in the
    submission graph (docx/zip ingestion through scoring) must run
    identically regardless of free_topic_request/skip_certificate_check, so
    a custom project is validated exactly as strictly as a catalog one. This
    is a regression guard: if a future change special-cases either flag
    inside the submission pipeline, this test fails loudly."""
    for node in _SUBMISSION_PIPELINE_NODES:
        source = inspect.getsource(node)
        assert "free_topic_request" not in source, f"{node.__name__} must not branch on free_topic_request"
        assert "skip_certificate_check" not in source, f"{node.__name__} must not branch on skip_certificate_check"
