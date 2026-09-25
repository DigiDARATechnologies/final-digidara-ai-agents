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
    # Not just "MISSING": what was missing, what belongs in it, and what to do.
    assert 'Your zip has no "output_screenshots" folder' in markdown
    assert "It should contain: screenshots." in markdown
    assert "TaskTracker/src" in markdown


def test_build_about_markdown_includes_required_paths_and_sections():
    state = {
        "chosen_topic": {"title": "Task Tracker", "summary": "A simple tracker."},
        "requirements": {
            "objective": "Help users track tasks.",
            "functional_requirements": ["Add a task", "Mark a task done"],
            "expected_deliverables": ["source code (.zip)", "written report (.docx)"],
        },
        "submission_guide": {
            "folder_structure": ["TaskTracker/", "TaskTracker/src/"],
            "required_paths": [{"path": "TaskTracker/src", "type": "dir", "description": "All source code."}],
            "docx_required_sections": ["Problem Statement", "Approach", "Conclusion"],
            "common_mistakes": ["Pasting code into the report"],
        },
    }
    markdown = build_about_markdown(state)
    assert "Task Tracker" in markdown
    assert "TaskTracker/src" in markdown
    assert "Problem Statement" in markdown and "Conclusion" in markdown
    assert "Do not put code or screenshots in the .docx report" in markdown


def test_about_markdown_explains_every_required_screenshot_in_detail_and_says_they_go_in_the_zip():
    state = {
        "chosen_topic": {"title": "Budget Tracker"},
        "requirements": {"functional_requirements": ["Show a pie chart of expenses by category"]},
        "submission_guide": {
            "folder_structure": ["BudgetTracker/", "BudgetTracker/src/", "BudgetTracker/output_screenshots/"],
            "required_paths": [{"path": "BudgetTracker/src", "type": "dir", "description": "Source."},
                               {"path": "BudgetTracker/output_screenshots", "type": "dir", "description": "Screenshots."}],
            "docx_required_sections": ["Problem Statement", "Approach", "Code", "Output Screenshots", "Conclusion"],
            "required_screenshots": [{
                "filename": "01-expense-pie-chart.png", "module": "Category summary page",
                "description": "the pie chart with at least two categories visible and their percentages",
                "how_to_capture": "Run python src/main.py, add three expenses in two categories, open Summary.",
                "linked_requirement": "Show a pie chart of expenses by category",
            }],
        },
    }
    markdown = build_about_markdown(state)
    assert "## Required Screenshots" in markdown and "output_screenshots" in markdown
    assert "`01-expense-pie-chart.png`" in markdown and "Category summary page" in markdown
    assert "What must be visible: the pie chart with at least two categories visible" in markdown
    assert "How to capture it: Run python src/main.py" in markdown
    assert "They go in the zip, NOT in the .docx report" in markdown
    # ...but as REPORT sections, "Code" and "Output Screenshots" are gone.
    assert "1. Problem Statement" in markdown and "2. Approach" in markdown and "3. Conclusion" in markdown
    assert "Do not put code or screenshots in the .docx report" in markdown


def test_review_markdown_lists_syntax_errors_with_the_offending_line():
    state = {
        "chosen_topic": {"title": "Budget Tracker"},
        "status": "needs_revision",
        "structure_score": {"is_complete": True},
        "syntax_report": {
            "checked_files": ["B/src/main.py"], "checked_languages": ["Python"], "unchecked_extensions": [".js"],
            "error_count": 1, "has_errors": True,
            "errors": [{
                "path": "B/src/main.py", "language": "Python", "line": 3, "column": 12,
                "message": "'(' was never closed", "source_line": "print(total",
            }],
        },
        "revision_notes": "",
    }
    markdown = build_review_markdown(state)
    assert "## Syntax Check" in markdown
    assert "Python syntax error in `B/src/main.py, line 3`" in markdown
    assert "'(' was never closed" in markdown
    assert "print(total" in markdown
    assert ".js files are not machine-checked" in markdown


def test_review_markdown_reports_a_clean_syntax_check():
    markdown = build_review_markdown({
        "chosen_topic": {"title": "T"}, "status": "needs_revision",
        "syntax_report": {"checked_files": ["a.py", "b.py"], "checked_languages": ["Python"], "errors": [], "error_count": 0},
    })
    assert "2 file(s) parsed with no syntax errors" in markdown


def test_review_markdown_lists_each_requirement_with_its_evidence():
    markdown = build_review_markdown({
        "chosen_topic": {"title": "T"}, "status": "needs_revision", "final_score": 50, "passed": False,
        "output_verification": {
            "output_correct": False, "confidence": "high",
            "requirements_check": [
                {"requirement": "Add an expense", "status": "met", "evidence": "tracker.add_expense"},
                {"requirement": "Export to CSV", "status": "not_met", "evidence": "no export code found"},
            ],
        },
    })
    assert "## Requirements Check" in markdown
    assert "✅ Add an expense — tracker.add_expense" in markdown
    assert "❌ Export to CSV — no export code found" in markdown


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


# --- syntax check: real parsers, deterministic --------------------------------

from app.ingestion.syntax_check import check_syntax  # noqa: E402
from app.ingestion.structure_check import (  # noqa: E402
    drop_retired_sections,
)


def test_syntax_check_accepts_valid_python_and_json():
    report = check_syntax({"app/main.py": "def add(a, b):\n    return a + b\n", "app/data.json": '{"a": [1, 2]}'})
    assert report["has_errors"] is False and report["errors"] == []
    assert report["checked_languages"] == ["JSON", "Python"]
    assert len(report["checked_files"]) == 2


def test_syntax_check_reports_the_file_line_column_and_source_line():
    report = check_syntax({"src/main.py": "x = 1\nprint(total\ny = 2\n"})
    assert report["has_errors"] is True and report["error_count"] == 1
    error = report["errors"][0]
    assert error["path"] == "src/main.py" and error["language"] == "Python"
    assert error["line"] in (2, 3)  # where the parser noticed the unclosed bracket
    assert error["message"]
    assert error["source_line"]


def test_syntax_check_catches_indentation_and_missing_colon_errors():
    report = check_syntax({
        "a.py": "def f():\nreturn 1\n",            # IndentationError
        "b.py": "if True\n    pass\n",               # missing colon
        "c.py": "print('fine')\n",
    })
    assert report["error_count"] == 2
    assert {error["path"] for error in report["errors"]} == {"a.py", "b.py"}


def test_syntax_check_flags_invalid_json_but_not_json_with_comments():
    report = check_syntax({
        "data.json": '{"a": 1,}',                          # trailing comma: invalid JSON
        "tsconfig.json": '{ // comments are fine here\n "a": 1 }',
    })
    assert [error["path"] for error in report["errors"]] == ["data.json"]
    assert report["errors"][0]["language"] == "JSON"


def test_syntax_check_lists_languages_it_cannot_check_instead_of_guessing():
    report = check_syntax({"web/app.js": "const x = a?.b ?? 1;", "Main.java": "class A {}", "README.md": "# hi"})
    assert report["has_errors"] is False and report["checked_files"] == []
    assert report["unchecked_extensions"] == [".java", ".js"]


def test_syntax_check_caps_the_reported_errors_but_counts_all_of_them():
    files = {f"f{i:02d}.py": "def (:\n" for i in range(30)}
    report = check_syntax(files)
    assert report["error_count"] == 30 and len(report["errors"]) == 20


def test_syntax_check_handles_empty_input_and_null_bytes():
    assert check_syntax({})["has_errors"] is False
    assert check_syntax(None)["has_errors"] is False
    assert check_syntax({"bad.py": "x = 1\x00"})["has_errors"] is True


def test_syntax_check_never_executes_the_submitted_code(tmp_path):
    marker = tmp_path / "ran.txt"
    source = f"open({str(marker)!r}, 'w').write('x')\n"
    check_syntax({"evil.py": source})
    assert not marker.exists()


def test_syntax_node_stores_the_report_and_the_gate_rejects_syntax_errors():
    result = nodes.syntax_check_node({"zip_code_files": {"a.py": "def (:\n"}})
    assert result["syntax_report"]["has_errors"] is True
    state = {"structure_score": {"is_complete": True}, **result}
    assert nodes.structure_gate_passed(state) is False
    clean = nodes.syntax_check_node({"zip_code_files": {"a.py": "x = 1\n"}})
    assert nodes.structure_gate_passed({"structure_score": {"is_complete": True}, **clean}) is True


def test_request_revision_with_only_syntax_errors_has_no_generic_revision_text(monkeypatch, database):
    monkeypatch.setattr(nodes, "build_review_markdown", lambda state: "review")
    state = {
        "submission_id": "missing", "structure_score": {"is_complete": True}, "zip_structure_score": {"is_complete": True},
        "syntax_report": {"has_errors": True, "errors": [{"path": "a.py", "language": "Python", "line": 1, "column": 1, "message": "bad", "source_line": "def (:"}]},
    }
    result = nodes.request_revision_node(state)
    assert result["status"] == "needs_revision"
    assert result["revision_notes"] == ""
    assert "Revision needed" not in result["revision_notes"] and "incomplete" not in result["revision_notes"]


# --- retired sections: an older guide stops requiring Code / Output Screenshots ---

def test_retired_sections_are_dropped_from_an_older_guide():
    assert drop_retired_sections(["Problem Statement", "Approach", "Code", "Output Screenshots", "Conclusion"]) == [
        "Problem Statement", "Approach", "Conclusion",
    ]
    assert drop_retired_sections(["1. Code", "2. Output Screenshots"]) == []
    assert drop_retired_sections(None) == []


def test_the_screenshots_folder_is_never_dropped_from_the_required_paths():
    from app.ingestion.screenshots import ensure_screenshot_folder
    guide = {
        "folder_structure": ["X/", "X/src/"],
        "required_paths": [{"path": "X/src", "type": "dir", "description": "code"}],
        "required_screenshots": [{"description": "the home page"}],
    }
    ensure_screenshot_folder(guide)
    assert {item["path"] for item in guide["required_paths"]} == {"X/src", "X/output_screenshots"}
    assert "X/output_screenshots/" in guide["folder_structure"]


def test_a_report_without_code_or_screenshots_passes_an_older_guide(monkeypatch):
    monkeypatch.setattr(nodes, "call_json", lambda **kwargs: {"is_complete": True, "weak_sections": [], "notes": ""})
    state = {
        "submission_guide": {"docx_required_sections": ["Problem Statement", "Approach", "Code", "Output Screenshots", "Conclusion"]},
        "doc_sections": {"1. Problem Statement": "Text.", "2. Approach": "Details.", "3. Conclusion": "Done."},
    }
    score = nodes.structure_validation_node(state)["structure_score"]
    assert score["is_complete"] is True
    assert score["missing_sections"] == []


def test_a_zip_without_a_screenshots_folder_reports_it_missing(monkeypatch):
    monkeypatch.setattr(nodes, "call_json", lambda **kwargs: {"structure_quality": "good", "clutter_flags": [], "notes": ""})
    state = {
        "submission_guide": {
            "folder_structure": ["X/", "X/src/", "X/output_screenshots/"],
            "required_paths": [{"path": "X/src", "type": "dir"}, {"path": "X/output_screenshots", "type": "dir"}],
        },
        "zip_file_tree": ["X/src/main.py"],
    }
    score = nodes.zip_structure_validation_node(state)["zip_structure_score"]
    assert score["is_complete"] is False
    assert score["missing_items"] == ["X/output_screenshots"]


def test_submission_guide_node_keeps_the_screenshots_but_fixes_the_report_sections(monkeypatch, database):
    monkeypatch.setattr(nodes, "call_json", lambda **kwargs: {
        "docx_required_sections": ["Problem Statement", "Approach", "Code", "Output Screenshots", "Conclusion"],
        "required_screenshots": [
            {"description": "the login form with an error", "module": "Login form"},   # no file name: one is made
            {"filename": "../../etc/passwd.png", "description": "the dashboard"},        # unsafe name: sanitised
            {"description": ""},                                                          # nothing to show: dropped
        ],
        "required_paths": [{"path": "X/src", "type": "dir"}],                             # the folder is missing: added
        "folder_structure": ["X/", "X/src/"],
    })
    state = {"assignment_id": "missing", "chosen_topic": {"title": "T"}, "requirements": {}}
    guide = nodes.submission_guide_node(state)["submission_guide"]
    assert guide["docx_required_sections"] == ["Problem Statement", "Approach", "Conclusion"]
    names = [item["filename"] for item in guide["required_screenshots"]]
    assert len(names) == 2 and names[0].startswith("01-") and names[0].endswith(".png")
    assert "/" not in names[1] and ".." not in names[1] and names[1].endswith(".png")
    assert {item["path"] for item in guide["required_paths"]} == {"X/src", "X/output_screenshots"}
    assert "X/output_screenshots/" in guide["folder_structure"]


# --- requirements verification: normalised by code, not trusted -----------------

def test_requirements_check_is_normalised_and_output_correct_is_arithmetic(monkeypatch):
    monkeypatch.setattr(nodes, "call_json", lambda **kwargs: {
        "output_correct": True,   # the model contradicts its own per-requirement verdicts
        "requirements_check": [
            {"requirement": "Add an expense", "status": "MET", "evidence": "tracker.py"},
            {"requirement": "Export to CSV", "status": "Not Met", "evidence": "missing"},
            {"requirement": "Reject bad input", "status": "looks fine to me"},   # unknown -> partial, never met
            {"status": "met"},                                                    # no requirement text: dropped
        ],
    })
    result = nodes.output_verification_node({"requirements": {}, "zip_code_files": {}})["output_verification"]
    assert [item["status"] for item in result["requirements_check"]] == ["met", "not_met", "partial"]
    assert result["output_correct"] is False
    assert "Export to CSV: not met" in result["requirements_demonstrated"]


def test_all_requirements_met_keeps_output_correct(monkeypatch):
    monkeypatch.setattr(nodes, "call_json", lambda **kwargs: {
        "output_correct": True,
        "requirements_check": [{"requirement": "Add an expense", "status": "met", "evidence": "x"}],
    })
    result = nodes.output_verification_node({"requirements": {}, "zip_code_files": {}})["output_verification"]
    assert result["output_correct"] is True


# --- the reviewers read ALL of the code -----------------------------------------

def test_code_prompt_includes_every_file_in_full_when_it_fits():
    from app.graph import prompts
    big = "x = 1\n" * 3000   # ~21k chars: well over the old 4000-char cut
    block = prompts._code_files_block({"a.py": big, "b.py": "print('b')\n"}, 160_000)
    assert big in block and "TRUNCATED" not in block


def test_code_prompt_trims_fairly_and_flags_it_when_over_budget():
    from app.graph import prompts
    files = {"small.py": "print('keep me whole')\n", "huge_a.py": "a" * 50_000, "huge_b.py": "b" * 50_000}
    block = prompts._code_files_block(files, 20_000)
    assert "print('keep me whole')" in block                 # small files are never cut
    assert block.count("TRUNCATED") == 2                      # both big ones are, and say so
    assert len(block) < 21_500


def test_scorer_and_verifier_prompts_get_the_requirements_and_the_syntax_report():
    from app.graph import prompts
    state = {
        "requirements": {"objective": "Track spending", "functional_requirements": ["Add an expense", "Show totals"],
                         "technical_constraints": ["Must run offline"]},
        "zip_code_files": {"src/main.py": "print(1)\n", "web/app.js": "let a = 1;\n"},
        "syntax_report": {"checked_files": ["src/main.py"], "checked_languages": ["Python"], "unchecked_extensions": [".js"]},
        "difficulty": "easy", "course_medium": "local",
    }
    for prompt in (prompts.code_quality_scorer_prompt(state), prompts.output_verification_prompt(state)):
        assert "1. Add an expense" in prompt and "2. Show totals" in prompt
        assert "Must run offline" in prompt
        assert "1 Python file(s) parsed with no syntax errors" in prompt
        assert "NOT machine-checked (.js files)" in prompt
        assert "src/main.py" in prompt and "web/app.js" in prompt


# --- clear, specific "what is missing and what to do" instructions ---------------

from app.graph import revision  # noqa: E402


def test_a_missing_section_says_what_belongs_in_it_and_how_to_add_it():
    text = revision.explain_missing_section("Approach")
    assert 'The "Approach" section is missing' in text
    assert "Heading 1" in text                         # how to make it detectable
    assert "design decisions" in text                  # what belongs in it
    assert "do not paste code" in text


def test_every_report_section_has_its_own_guidance_and_unknown_ones_get_a_fallback():
    assert "who has it" in revision.explain_missing_section("Problem Statement")
    assert "limitations" in revision.explain_missing_section("2. Conclusion")   # numbered heading still recognised
    assert "several full sentences" in revision.explain_missing_section("Testing Strategy")


def test_a_missing_folder_is_never_just_reported_as_missing():
    text = revision.explain_missing_path(
        {"path": "TaskTracker/src", "type": "dir", "description": "All the source code of the tracker."})
    assert 'no "src" folder' in text
    assert "TaskTracker/src" in text                   # exactly what was looked for
    assert "It should contain: All the source code of the tracker." in text
    assert "move the matching files into it" in text and "zip the project again" in text


def test_a_missing_file_says_where_to_add_it():
    text = revision.explain_missing_path({"path": "TaskTracker/README.md", "type": "file", "description": "How to run it."})
    assert 'no "README.md" file' in text and "Add the file at TaskTracker/README.md" in text


def test_an_unmet_requirement_names_it_says_what_is_missing_and_what_to_do():
    text = revision.explain_requirement(
        {"requirement": "Export the expenses to CSV", "status": "not_met", "evidence": "no export function exists anywhere"})
    assert 'Requirement is not implemented:** "Export the expenses to CSV"' in text
    assert "No export function exists anywhere." in text
    assert "upload the zip again" in text
    partial = revision.explain_requirement({"requirement": "Show totals", "status": "partial", "evidence": "monthly totals are missing"})
    assert "only partly implemented" in partial


def test_revision_items_lists_every_problem_specifically():
    state = {
        "structure_score": {"missing_sections": ["Conclusion"], "weak_sections": ["Approach: only two sentences, no design decisions"]},
        "zip_structure_score": {"required_paths_detail": {"missing_items": [
            {"path": "T/src", "type": "dir", "description": "Source code."},
            {"path": "T/output_screenshots", "type": "dir", "description": "Screenshots."},
        ]}},
    }
    items = revision.revision_items(state)
    assert len(items) == 4
    assert 'The "Conclusion" section is missing' in items[0]
    assert 'The "Approach" section needs more detail.** only two sentences, no design decisions' in items[1]
    assert 'no "src" folder' in items[2]
    assert 'no "output_screenshots" folder' in items[3]


def test_request_revision_node_gives_bulleted_specific_instructions(monkeypatch, database):
    monkeypatch.setattr(nodes, "build_review_markdown", lambda state: "review")
    state = {
        "submission_id": "missing",
        "structure_score": {"is_complete": False, "missing_sections": ["Approach"], "notes": "vague reviewer note"},
        "zip_structure_score": {"is_complete": False, "notes": "vague zip note",
                                "required_paths_detail": {"missing_items": [{"path": "T/src", "type": "dir", "description": "Source code."}]}},
    }
    notes = nodes.request_revision_node(state)["revision_notes"]
    lines = notes.splitlines()
    assert len(lines) == 2 and all(line.startswith("- ") for line in lines)
    assert 'The "Approach" section is missing' in lines[0]
    assert 'no "src" folder' in lines[1]
    assert "vague" not in notes                                    # the specifics replace the paraphrase


def test_a_failed_grade_appends_the_exact_fix_list_to_the_feedback(monkeypatch, database):
    monkeypatch.setattr(nodes, "call_text", lambda **kwargs: "You did not pass this time.")
    state = {
        "passed": False, "final_score": 41, "submission_id": "missing", "assignment_id": "missing",
        "student_name": "Learner", "chosen_topic": {"title": "T"},
        "output_verification": {"requirements_check": [
            {"requirement": "Add an expense", "status": "met", "evidence": "x"},
            {"requirement": "Export to CSV", "status": "not_met", "evidence": "no export code"},
        ]},
    }
    result = nodes.feedback_generator_node(state)
    assert result["feedback"].startswith("You did not pass this time.")
    assert "### What to fix before you resubmit" in result["feedback"]
    assert 'Requirement is not implemented:** "Export to CSV"' in result["feedback"]
    assert "Add an expense" not in result["feedback"].split("### What to fix")[1]     # met ones are not listed
    assert result["revision_notes"] == result["feedback"]


def test_a_passing_grade_gets_no_fix_list(monkeypatch, database):
    monkeypatch.setattr(nodes, "call_text", lambda **kwargs: "Great work.")
    state = {"passed": True, "final_score": 90, "submission_id": "missing", "assignment_id": "missing",
             "student_name": "L", "chosen_topic": {"title": "T"},
             "output_verification": {"requirements_check": [{"requirement": "A", "status": "partial", "evidence": "x"}]}}
    assert nodes.feedback_generator_node(state)["feedback"] == "Great work."


def test_the_review_report_uses_the_same_specific_wording():
    markdown = build_review_markdown({
        "chosen_topic": {"title": "T"}, "status": "needs_revision",
        "structure_score": {"is_complete": False, "missing_sections": ["Conclusion"], "matched_sections": ["Approach"]},
        "zip_structure_score": {"required_paths_detail": {"missing_items": [{"path": "T/src", "type": "dir", "description": "Source code."}]}},
    })
    assert 'The "Conclusion" section is missing from your report' in markdown
    assert 'Your zip has no "src" folder' in markdown and "It should contain: Source code." in markdown


def test_a_zip_with_no_code_says_what_was_found_and_where_code_should_go(tmp_path):
    import zipfile
    from app.ingestion.zip_ingest import ZipIngestError, ingest_zip
    archive = tmp_path / "docs_only.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("Proj/notes.pdf", "x")
        zf.writestr("Proj/logo.png", "x")
    try:
        ingest_zip(str(archive))
    except ZipIngestError as exc:
        message = str(exc)
    else:
        raise AssertionError("a zip with no source code must be rejected")
    assert "no source code files we can read" in message
    assert "src folder" in message and "MyProject/src/main.py" in message
    assert "Proj/notes.pdf" in message and "Proj/logo.png" in message   # what WAS in the zip
