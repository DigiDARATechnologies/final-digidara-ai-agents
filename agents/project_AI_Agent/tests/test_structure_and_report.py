from app.graph import nodes
from app.graph.report import build_about_markdown, build_review_markdown
from app.ingestion.structure_check import check_required_paths


REQUIRED_PATHS = [
    {"path": "TaskTracker/src", "type": "dir", "description": "All your source code."},
    {"path": "TaskTracker/output_screenshots", "type": "dir", "description": "Screenshots of the app running."},
]


def test_check_required_paths_all_present():
    tree = ["TaskTracker/src/main.py", "TaskTracker/output_screenshots/run1.png"]
    result = check_required_paths(REQUIRED_PATHS, tree)
    assert result["is_complete"] is True
    assert result["missing_items"] == []
    assert {item["path"] for item in result["matched_items"]} == {p["path"] for p in REQUIRED_PATHS}


def test_check_required_paths_detects_missing_folder():
    tree = ["TaskTracker/main.py"]  # no src/ or output_screenshots/ at all
    result = check_required_paths(REQUIRED_PATHS, tree)
    assert result["is_complete"] is False
    missing_paths = {item["path"] for item in result["missing_items"]}
    assert missing_paths == {"TaskTracker/src", "TaskTracker/output_screenshots"}


def test_check_required_paths_tolerates_different_root_folder_name():
    # Student named their root folder differently than the guide's slug --
    # the trailing segment ("src"/"output_screenshots") is what's checked,
    # not the exact suggested root prefix.
    tree = ["my-cool-project/src/app.py", "my-cool-project/output_screenshots/ok.png"]
    result = check_required_paths(REQUIRED_PATHS, tree)
    assert result["is_complete"] is True


def test_check_required_paths_is_deterministic_across_repeated_calls():
    tree = ["TaskTracker/main.py"]
    first = check_required_paths(REQUIRED_PATHS, tree)
    second = check_required_paths(REQUIRED_PATHS, tree)
    assert first == second


def test_zip_structure_validation_node_ignores_llm_presence_claims(monkeypatch):
    """The LLM might (incorrectly) claim something is missing/complete in its
    own JSON -- the node must always use the deterministic result for
    is_complete/missing_items regardless of what the LLM returns."""
    monkeypatch.setattr(
        nodes,
        "call_json",
        lambda **kwargs: {"is_complete": False, "missing_items": ["some LLM hallucination"], "structure_quality": "poor", "notes": "bad"},
    )
    state = {
        "submission_guide": {"required_paths": REQUIRED_PATHS, "folder_structure": []},
        "zip_file_tree": ["TaskTracker/src/main.py", "TaskTracker/output_screenshots/run1.png"],
    }
    result = nodes.zip_structure_validation_node(state)
    score = result["zip_structure_score"]
    assert score["is_complete"] is True  # deterministic result wins, not the LLM's claim
    assert score["missing_items"] == []


def test_build_review_markdown_lists_missing_required_paths():
    state = {
        "chosen_topic": {"title": "Task Tracker"},
        "status": "needs_revision",
        "structure_score": {"is_complete": True},
        "zip_structure_score": {
            "required_paths_detail": {
                "matched_items": [{"path": "TaskTracker/src", "type": "dir", "description": "source code"}],
                "missing_items": [{"path": "TaskTracker/output_screenshots", "type": "dir", "description": "screenshots"}],
            },
            "notes": "Add the missing folder.",
        },
        "revision_notes": "Code zip: Add the missing folder.",
    }
    markdown = build_review_markdown(state)
    assert "TaskTracker/output_screenshots" in markdown
    assert "MISSING" in markdown
    assert "TaskTracker/src" in markdown


def test_build_about_markdown_includes_required_paths_and_sections():
    state = {
        "chosen_topic": {"title": "Task Tracker", "summary": "A simple tracker."},
        "requirements": {
            "objective": "Help users track tasks.",
            "functional_requirements": ["Add a task", "Mark a task done"],
            "expected_deliverables": ["source code", "output screenshots"],
        },
        "submission_guide": {
            "folder_structure": ["TaskTracker/", "TaskTracker/src/", "TaskTracker/output_screenshots/"],
            "required_paths": REQUIRED_PATHS,
            "docx_required_sections": ["Problem Statement", "Approach"],
            "common_mistakes": ["Forgetting screenshots"],
        },
    }
    markdown = build_about_markdown(state)
    assert "Task Tracker" in markdown
    assert "TaskTracker/src" in markdown
    assert "output_screenshots" in markdown
    assert "Problem Statement" in markdown
