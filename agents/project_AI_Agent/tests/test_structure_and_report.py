from app.graph import nodes
from app.graph.report import build_about_markdown, build_review_markdown
from app.ingestion.structure_check import check_required_paths, check_required_sections


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


def test_build_about_markdown_lists_required_screenshots():
    state = {
        "chosen_topic": {"title": "Budget Tracker"},
        "requirements": {"functional_requirements": ["Show a pie chart of expenses by category"]},
        "submission_guide": {
            "required_screenshots": [
                {
                    "description": "Pie chart of expenses by category with at least two categories visible",
                    "linked_requirement": "Show a pie chart of expenses by category",
                }
            ],
        },
    }
    markdown = build_about_markdown(state)
    assert "Required Screenshots" in markdown
    assert "Pie chart of expenses by category" in markdown
    assert "Show a pie chart of expenses by category" in markdown


def test_build_review_markdown_lists_missing_screenshots():
    state = {
        "chosen_topic": {"title": "Budget Tracker"},
        "status": "needs_revision",
        "structure_score": {
            "is_complete": False,
            "missing_screenshots": ["Pie chart of expenses by category"],
            "notes": "Add the pie chart screenshot.",
        },
        "revision_notes": "Report: Add the pie chart screenshot.",
    }
    markdown = build_review_markdown(state)
    assert "Missing screenshot: Pie chart of expenses by category" in markdown


# --- docx section presence: deterministic, not LLM-judged --------------------

def test_check_required_sections_matches_numbered_heading():
    # Regression case: a student's real heading was literally "2. Approach"
    # (Word auto-numbering) while the guide's requirement is the plain name
    # "Approach" -- these must be recognized as the same section.
    doc_sections = {"1. Problem Statement": "...", "2. Approach": "Architecture details here.", "3. Code": "..."}
    result = check_required_sections(["Problem Statement", "Approach", "Code"], doc_sections)
    assert result["is_complete"] is True
    assert result["missing_sections"] == []
    assert "Approach" in result["matched_sections"]


def test_check_required_sections_detects_genuinely_missing_section():
    doc_sections = {"1. Problem Statement": "...", "2. Code": "..."}
    result = check_required_sections(["Problem Statement", "Approach", "Code"], doc_sections)
    assert result["is_complete"] is False
    assert result["missing_sections"] == ["Approach"]


def test_check_required_sections_matches_broader_heading_text():
    doc_sections = {"Approach & Design Rationale": "Details."}
    result = check_required_sections(["Approach"], doc_sections)
    assert result["is_complete"] is True


def test_structure_validation_node_ignores_llm_hallucinated_missing_section(monkeypatch):
    """Even if the LLM's own JSON claims a section is missing, the node must
    use the deterministic result -- this is the exact bug from production:
    a real "2. Approach" heading got reported as a missing 'Approach'
    section because presence used to be entirely LLM-judged."""
    monkeypatch.setattr(
        nodes, "call_json",
        lambda **kwargs: {"is_complete": True, "weak_sections": [], "screenshots_present": True, "notes": ""},
    )
    state = {
        "submission_guide": {"docx_required_sections": ["Problem Statement", "Approach"]},
        "doc_sections": {"1. Problem Statement": "Text.", "2. Approach": "Architecture and UI flow details."},
        "screenshot_ocr_text": "none",
        "screenshots_present": True,
    }
    result = nodes.structure_validation_node(state)
    score = result["structure_score"]
    assert score["is_complete"] is True
    assert score["missing_sections"] == []
    assert "Approach" in score["matched_sections"]


def test_structure_validation_node_still_fails_on_genuinely_missing_section(monkeypatch):
    """The reverse direction: even if the LLM (wrongly) claims completeness,
    a truly absent required section must still fail the deterministic check."""
    monkeypatch.setattr(
        nodes, "call_json",
        lambda **kwargs: {"is_complete": True, "weak_sections": [], "screenshots_present": True, "notes": ""},
    )
    state = {
        "submission_guide": {"docx_required_sections": ["Problem Statement", "Approach"]},
        "doc_sections": {"1. Problem Statement": "Text."},
        "screenshot_ocr_text": "none",
        "screenshots_present": True,
    }
    result = nodes.structure_validation_node(state)
    score = result["structure_score"]
    assert score["is_complete"] is False
    assert score["missing_sections"] == ["Approach"]


# --- final pass/fail: deterministic threshold, not a second LLM judgment -----

def test_score_aggregator_node_ignores_llm_passed_claim_below_threshold(monkeypatch):
    """The LLM might (wrongly, or via its own variance) claim `passed: true`
    for a score under the threshold -- pass/fail must be decided purely by
    comparing final_score to config.PASS_THRESHOLD, not trusted from the
    LLM's own JSON, so the same score always gets the same verdict."""
    from app import config as app_config
    monkeypatch.setattr(app_config, "PASS_THRESHOLD", 70)
    monkeypatch.setattr(nodes.config, "PASS_THRESHOLD", 70)
    monkeypatch.setattr(nodes, "call_json", lambda **kwargs: {"final_score": 65.0, "passed": True, "reasoning": "looks fine"})
    result = nodes.score_aggregator_node({})
    assert result["final_score"] == 65.0
    assert result["passed"] is False


def test_score_aggregator_node_passes_at_or_above_threshold(monkeypatch):
    from app import config as app_config
    monkeypatch.setattr(app_config, "PASS_THRESHOLD", 70)
    monkeypatch.setattr(nodes.config, "PASS_THRESHOLD", 70)
    monkeypatch.setattr(nodes, "call_json", lambda **kwargs: {"final_score": 70.0, "reasoning": "solid submission"})
    result = nodes.score_aggregator_node({})
    assert result["passed"] is True


def test_score_aggregator_node_is_deterministic_across_repeated_calls(monkeypatch):
    from app import config as app_config
    monkeypatch.setattr(app_config, "PASS_THRESHOLD", 70)
    monkeypatch.setattr(nodes.config, "PASS_THRESHOLD", 70)
    monkeypatch.setattr(nodes, "call_json", lambda **kwargs: {"final_score": 69.9, "reasoning": "just under"})
    first = nodes.score_aggregator_node({})
    second = nodes.score_aggregator_node({})
    assert first == second == {"final_score": 69.9, "passed": False, "score_reasoning": "just under"}
