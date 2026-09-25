"""All 14 LangGraph nodes. Each node is `def node(state: ProjectAgentState) -> dict`
returning only the keys it updates, per LangGraph convention."""
from __future__ import annotations

import functools
import logging
import random
import time
from datetime import datetime, timedelta, timezone

from app import config
from app.db.database import get_session
from app.db.models import (
    AssignmentStatus,
    ProjectAssignment,
    Submission,
    SubmissionStatus,
)
from app.execution.browser_check import BrowserCheckUnavailable, run_html_submission
from app.execution.entry_point import find_html_entry_point, find_node_entry_point, find_python_entry_point
from app.execution.judge0_client import Judge0Unavailable, run_node_submission, run_python_submission
from app.graph import prompts, revision
from app.graph.report import build_about_markdown, build_review_markdown
from app.graph.state import ProjectAgentState
from app.ingestion.docx_ingest import DocxIngestError, ingest_docx
from app.ingestion.structure_check import (
    REPORT_SECTIONS,
    check_required_paths,
    check_required_sections,
    drop_retired_sections,
)
from app.ingestion.screenshots import ensure_screenshot_folder, normalise_required_screenshots, screenshot_status
from app.ingestion.syntax_check import check_syntax
from app.ingestion.zip_ingest import ZipIngestError, ingest_zip
from app.llm.client import call_json, call_text

# Grading/validation calls want maximally consistent, repeatable judgments —
# lower than call_json's own default (0.2) and set explicitly at every
# scoring/validation call site below so the intent is visible at each call,
# not just implied by whatever the shared default happens to be.
_SCORING_TEMPERATURE = 0.1

logger = logging.getLogger("capstone.graph")

_ID_KEYS = ("assignment_id", "submission_id", "thread_id")


def log_node(fn):
    """Logs entry/exit of every graph node: which ids it's operating on, how
    long it took, and which state keys it returned (or the exception if it
    failed) — the terminal trace of "what is the agent doing right now"."""

    @functools.wraps(fn)
    def wrapper(state: ProjectAgentState) -> dict:
        ids = {k: state[k] for k in _ID_KEYS if k in state}
        logger.info("-> %s starting %s", fn.__name__, ids)
        started = time.perf_counter()
        try:
            result = fn(state)
        except Exception:
            elapsed = time.perf_counter() - started
            logger.exception("x  %s failed after %.2fs", fn.__name__, elapsed)
            raise
        elapsed = time.perf_counter() - started
        logger.info("<- %s done in %.2fs, returned: %s", fn.__name__, elapsed, list(result.keys()))
        return result

    return wrapper


# --- Node 1: TopicGeneratorNode (LLM) ---------------------------------------

_TOPIC_ANGLES = [
    "personal productivity or habit tracking",
    "a small local business or freelancer use case",
    "a hobby or lifestyle interest (fitness, cooking, gaming, music, reading)",
    "an educational or study-aid tool",
    "a household or family organization tool",
    "an environmental or sustainability angle",
    "a community or local-event use case",
    "a creative or content-generation tool",
    "a simple automation for a repetitive daily task",
    "a data-driven decision-making tool for a niche audience",
]


@log_node
def topic_generator_node(state: ProjectAgentState) -> dict:
    """Two levers keep this from generating the same pair of topics every
    time: (1) an explicit "don't repeat these" list built from every past
    chosen topic for this course, and (2) a higher temperature plus a
    randomly-picked steering angle — low temperature is what made every run
    converge on the same generic textbook example for a given course+medium."""
    session = get_session()
    try:
        past_assignments = (
            session.query(ProjectAssignment)
            .filter(
                ProjectAssignment.course_id == state["course_id"],
                ProjectAssignment.topic_json.isnot(None),
            )
            .order_by(ProjectAssignment.created_at.desc())
            .limit(20)
            .all()
        )
        past_titles = sorted(
            {a.topic_json["title"] for a in past_assignments if a.topic_json and a.topic_json.get("title")}
        )
    finally:
        session.close()

    # A free-text request already carries its own angle (whatever the student
    # actually asked for) — injecting a random generic one on top of it is
    # what causes replies disconnected from the request (e.g. a "TCS
    # interview, Python developer role" prompt coming back as a Flashcard
    # Study App because "an educational or study-aid tool" got rolled). Only
    # a real course name is underspecified enough to need that steering.
    angle_hint = None if state.get("free_topic_request") else random.choice(_TOPIC_ANGLES)
    # Free-topic requests are exactly the ones that name something web
    # search can actually ground (a company, a current role/tech-stack
    # expectation) — a real course name has no such external reality to
    # check against, so search would just add cost/latency for nothing.
    use_web_search = bool(state.get("free_topic_request")) and config.ENABLE_TOPIC_WEB_SEARCH
    result = call_json(
        system=prompts.topic_generator_prompt(state, past_titles, angle_hint),
        user="Generate the two topic options now.",
        temperature=0.9,
        web_search=use_web_search,
    )
    return {"topic_options": result.get("options", [])}


# --- Node 3: RequirementExpansionNode (LLM) ---------------------------------

@log_node
def requirement_expansion_node(state: ProjectAgentState) -> dict:
    result = call_json(
        system=prompts.requirement_expansion_prompt(state),
        user="Write the full requirements brief now.",
    )

    # Persisted (not just kept in the LangGraph checkpoint) so the Q&A agent
    # can answer a doubt about the requirements as soon as they're shown --
    # including before the timer is confirmed, when about_markdown doesn't
    # exist yet.
    session = get_session()
    try:
        assignment = session.get(ProjectAssignment, state["assignment_id"])
        if assignment:
            assignment.requirements_json = result
            session.commit()
    finally:
        session.close()

    return {"requirements": result}


# --- Node 4: TimerInitNode (deterministic) ----------------------------------

@log_node
def timer_init_node(state: ProjectAgentState) -> dict:
    now = datetime.now(timezone.utc)
    deadline = now + timedelta(days=config.SUBMISSION_WINDOW_DAYS)

    session = get_session()
    try:
        assignment = session.get(ProjectAssignment, state["assignment_id"])
        assignment.topic_json = state["chosen_topic"]
        assignment.chosen_at = now
        assignment.deadline_at = deadline
        assignment.status = AssignmentStatus.in_progress
        session.commit()
    finally:
        session.close()

    return {"deadline_at": deadline.isoformat()}


# --- Node 5: SubmissionGuideNode (LLM) --------------------------------------

@log_node
def submission_guide_node(state: ProjectAgentState) -> dict:
    result = call_json(
        system=prompts.submission_guide_prompt(state),
        user="Write the submission guide now.",
    )
    # What the report needs is decided here, not by the model: exactly three
    # sections, no code and no screenshots inside the .docx. A model that wandered
    # back to the old five-section layout is overridden.
    result["docx_required_sections"] = list(REPORT_SECTIONS)
    # The screenshots belong in the ZIP's output_screenshots folder. Each one gets a
    # concrete file name, and the folder is guaranteed to be a required path.
    result["required_screenshots"] = normalise_required_screenshots(result.get("required_screenshots"))
    ensure_screenshot_folder(result)
    about_markdown = build_about_markdown({**state, "submission_guide": result})

    session = get_session()
    try:
        assignment = session.get(ProjectAssignment, state["assignment_id"])
        if assignment:
            assignment.about_markdown = about_markdown
            session.commit()
    finally:
        session.close()

    return {"submission_guide": result, "about_markdown": about_markdown}


# --- Node 6: DocxIngestNode (deterministic) ---------------------------------

@log_node
def docx_ingest_node(state: ProjectAgentState) -> dict:
    try:
        parsed = ingest_docx(state["docx_path"])
    except DocxIngestError as exc:
        return {"status": "error", "feedback": str(exc)}
    return {"doc_sections": parsed["sections"]}


# --- Node 7: ZipIngestNode (deterministic) ----------------------------------

@log_node
def zip_ingest_node(state: ProjectAgentState) -> dict:
    try:
        parsed = ingest_zip(state["zip_path"])
    except ZipIngestError as exc:
        return {"status": "error", "feedback": str(exc)}
    return {
        "zip_file_tree": parsed["zip_file_tree"],
        "zip_code_files": parsed["zip_code_files"],
        "screenshot_evidence": parsed["screenshot_evidence"],
    }


# --- SyntaxCheckNode (deterministic) ---------------------------------------

@log_node
def syntax_check_node(state: ProjectAgentState) -> dict:
    """Parse every checkable source file in the zip (Python, JSON, TOML) with a
    real parser. Errors here are facts, not LLM opinion, and send the submission
    back for another upload before any scoring happens. See
    app/ingestion/syntax_check.py for what is and isn't covered."""
    return {"syntax_report": check_syntax(state.get("zip_code_files"))}


# --- Node 8: StructureValidationNode (deterministic presence check + LLM content quality) ---

@log_node
def structure_validation_node(state: ProjectAgentState) -> dict:
    guide = state.get("submission_guide") or {}
    required_sections = drop_retired_sections(guide.get("docx_required_sections"))
    deterministic = check_required_sections(required_sections, state.get("doc_sections"))

    result = call_json(
        system=prompts.structure_validation_prompt(state, deterministic),
        user="Validate the document structure now.",
        temperature=_SCORING_TEMPERATURE,
    )
    # Whether a required section EXISTS is decided by check_required_sections, never
    # by the LLM (see app/ingestion/structure_check.py) -- an auto-numbered heading
    # like "2. Approach" must always match a plain "Approach" requirement the same
    # way on every run, not depend on the model noticing it that particular time.
    # The LLM's own is_complete is content-quality judgment ONLY (weak/placeholder
    # sections, screenshot evidence); the final verdict requires both to pass.
    result["missing_sections"] = deterministic["missing_sections"]
    result["matched_sections"] = deterministic["matched_sections"]
    result["is_complete"] = deterministic["is_complete"] and bool(result.get("is_complete", True))
    return {"structure_score": result}


# --- Node 9: ZipStructureValidationNode (deterministic presence check + LLM commentary) ---

@log_node
def zip_structure_validation_node(state: ProjectAgentState) -> dict:
    guide = state.get("submission_guide") or {}
    deterministic = check_required_paths(guide.get("required_paths"), state.get("zip_file_tree"))

    result = call_json(
        system=prompts.zip_structure_validation_prompt(state, deterministic),
        user="Validate the zip folder structure now.",
        temperature=_SCORING_TEMPERATURE,
    )
    # Presence/absence of required paths is decided by check_required_paths, never
    # by the LLM (see app/ingestion/structure_check.py) -- this is what makes the
    # same zip always get the same "missing folder" verdict on resubmission. The
    # LLM call above only supplies clutter_flags/structure_quality/notes on top.
    result["is_complete"] = deterministic["is_complete"]
    result["missing_items"] = [item["path"] for item in deterministic["missing_items"]]
    result["matched_items"] = [item["path"] for item in deterministic["matched_items"]]
    result["required_paths_detail"] = deterministic
    return {"zip_structure_score": result}


def structure_gate_passed(state: ProjectAgentState) -> bool:
    """Only the .docx report's structure is a hard gate — a report missing
    required sections genuinely isn't gradable content. Zip *folder*
    structure/naming is deliberately NOT a gate: a student who wrote
    working, correct code shouldn't get auto-rejected before that code is
    even looked at just because they organized files differently than the
    suggested layout. zip_structure_score still reaches the student (via
    feedback_generator_prompt) and still affects the STRUCTURE axis of
    code_quality_scorer_prompt — it's a scoring input, not a rejection
    reason. (A zip with no real source files at all never reaches this
    check either way — zip_ingest_node already hard-stops on that.)"""
    if state.get("status") == "error":
        return False
    # A file that does not even parse is not gradable code either: it goes back
    # for another upload instead of being scored.
    if (state.get("syntax_report") or {}).get("has_errors"):
        return False
    # The screenshots the project needs must actually be in the zip (a count of
    # real, readable images -- see app/ingestion/screenshots.py). A missing
    # screenshots folder is the extreme case of this, and is explained on its own.
    if not screenshot_status(state.get("submission_guide") or {}, state.get("screenshot_evidence"))["complete"]:
        return False
    return bool(state.get("structure_score", {}).get("is_complete"))


# --- Node: CodeExecutionNode (deterministic, best-effort sandboxed run) -----

@log_node
def code_execution_node(state: ProjectAgentState) -> dict:
    """Best-effort supplementary evidence for OutputVerificationNode and
    CodeQualityScorerNode: actually run the submission (or, for a static
    page, load it in a headless browser) and capture real evidence — stdout/
    stderr/exit status for Python and Node, console/page errors for HTML —
    instead of trusting only the LLM's static read of the code plus the
    student's own screenshots. Never a hard gate.

    Tries each medium's entry-point detector in turn and stops at the first
    match: Python (Judge0), then Node (Judge0), then a static HTML page
    (headless browser). A project genuinely has at most one of these — a
    Flask app has a .py entry, a static site has an index.html and no
    server-side entry — so first-match-wins doesn't have real ambiguity to
    resolve, it's just checking which kind of project this is."""
    code_files = state.get("zip_code_files") or {}

    entry_point = find_python_entry_point(code_files)
    if entry_point:
        try:
            return {"execution_result": run_python_submission(code_files, entry_point)}
        except Judge0Unavailable:
            return {"execution_result": {"available": False, "reason": "Execution sandbox (Judge0) is not reachable."}}

    entry_point = find_node_entry_point(code_files)
    if entry_point:
        try:
            return {"execution_result": run_node_submission(code_files, entry_point)}
        except Judge0Unavailable:
            return {"execution_result": {"available": False, "reason": "Execution sandbox (Judge0) is not reachable."}}

    entry_point = find_html_entry_point(code_files)
    if entry_point:
        try:
            return {"execution_result": run_html_submission(state["zip_path"], entry_point)}
        except BrowserCheckUnavailable as exc:
            return {"execution_result": {"available": False, "reason": f"Headless browser check unavailable: {exc}"}}

    return {"execution_result": {"available": False, "reason": "No runnable entry point (Python, Node, or HTML) detected."}}


# --- RequestRevisionNode (deterministic) ------------------------------------

@log_node
def request_revision_node(state: ProjectAgentState) -> dict:
    structure = state.get("structure_score", {})
    zip_structure = state.get("zip_structure_score", {})
    # Each problem is spelled out: WHAT is missing, what belongs in it and what
    # to do about it (see app/graph/revision.py) -- not just "src folder is
    # missing" or the reviewers' paraphrase.
    notes = revision.revision_items(state)
    # Syntax errors are NOT folded into these notes: they travel as structured
    # data (syntax_report.errors) so the chat can show each one the way a
    # terminal would, and the review report lists them in their own section.
    # With syntax errors as the only problem there is nothing else to say.
    if (state.get("syntax_report") or {}).get("has_errors"):
        revision_notes = revision.as_bullets(notes)
    else:
        revision_notes = revision.as_bullets(notes) or "Submission is incomplete — see validation notes."
    review_markdown = build_review_markdown({**state, "status": "needs_revision", "revision_notes": revision_notes})

    session = get_session()
    try:
        submission = session.get(Submission, state["submission_id"])
        if submission:
            submission.status = SubmissionStatus.needs_revision
            submission.docx_validation_json = structure
            submission.zip_validation_json = zip_structure
            submission.review_markdown = review_markdown
            session.commit()
    finally:
        session.close()

    return {"status": "needs_revision", "revision_notes": revision_notes, "review_markdown": review_markdown}


_REQUIREMENT_STATUSES = {"met", "partial", "not_met"}


_SCREENSHOT_STATUSES = {"present", "unclear", "missing"}


def _normalise_screenshots_check(items) -> list[dict]:
    """Same idea as the requirements check: a closed set of statuses, and anything
    unrecognised is "unclear" -- never silently "present"."""
    checks = []
    for item in items or []:
        if not isinstance(item, dict) or not str(item.get("screenshot", "")).strip():
            continue
        status = str(item.get("status", "")).strip().lower()
        checks.append({
            "screenshot": str(item["screenshot"]).strip(),
            "status": status if status in _SCREENSHOT_STATUSES else "unclear",
            "evidence": str(item.get("evidence", "")).strip(),
        })
    return checks


def _normalise_requirements_check(items) -> list[dict]:
    """Coerce the model's per-requirement verdicts into a clean, closed set of
    statuses. An unrecognised status is treated as "partial" -- never silently as
    "met", since "met" is the one verdict that has to be earned."""
    checks = []
    for item in items or []:
        if not isinstance(item, dict) or not str(item.get("requirement", "")).strip():
            continue
        status = str(item.get("status", "")).strip().lower().replace(" ", "_").replace("-", "_")
        checks.append({
            "requirement": str(item["requirement"]).strip(),
            "status": status if status in _REQUIREMENT_STATUSES else "partial",
            "evidence": str(item.get("evidence", "")).strip(),
        })
    return checks


# --- Node 10: OutputVerificationNode (LLM, reads the full code) --------------

@log_node
def output_verification_node(state: ProjectAgentState) -> dict:
    result = call_json(
        system=prompts.output_verification_prompt(state),
        user="Verify the requirements against the code now.",
        temperature=_SCORING_TEMPERATURE,
    )
    checks = _normalise_requirements_check(result.get("requirements_check"))
    result["requirements_check"] = checks
    result["screenshots_check"] = _normalise_screenshots_check(result.get("screenshots_check"))
    # Kept in the shape the report and the score aggregator already read.
    result["requirements_demonstrated"] = [
        f"{item['requirement']}: {item['status'].replace('_', ' ')}" for item in checks
    ]
    # "Every requirement is met" is arithmetic over the per-requirement verdicts,
    # so a model that lists a requirement as not met can't also declare the
    # output correct.
    if checks and any(item["status"] != "met" for item in checks):
        result["output_correct"] = False
    return {"output_verification": result}


# --- Node 11: CodeQualityScorerNode (LLM) -----------------------------------

@log_node
def code_quality_scorer_node(state: ProjectAgentState) -> dict:
    result = call_json(
        system=prompts.code_quality_scorer_prompt(state),
        user="Score the code quality now.",
        temperature=_SCORING_TEMPERATURE,
    )
    if "total_code_score" not in result:
        result["total_code_score"] = sum(
            result.get(k, 0)
            for k in ("structure_score", "syntax_score", "maintainability_score", "completeness_score")
        )
    return {"code_quality_score": result}


# --- Node 12: ScoreAggregatorNode (LLM decides the final score AND pass/fail) ---

@log_node
def score_aggregator_node(state: ProjectAgentState) -> dict:
    result = call_json(
        system=prompts.final_score_decision_prompt(state, config.PASS_THRESHOLD),
        user="Decide the final score now.",
        temperature=_SCORING_TEMPERATURE,
    )
    final_score = float(result.get("final_score", 0))
    # Pass/fail is a deterministic threshold comparison, not a second
    # independent LLM judgment call -- letting the model decide "passed"
    # on top of (and potentially disagreeing with) its own score meant two
    # submissions with the identical final_score could get different
    # verdicts purely from LLM variance, with no way for a student to
    # understand why. The score itself is still the LLM's qualitative call;
    # only the pass/fail line drawn on top of it is deterministic now.
    return {
        "final_score": final_score,
        "passed": final_score >= config.PASS_THRESHOLD,
        "score_reasoning": result.get("reasoning", ""),
    }


# --- Node 13: FeedbackGeneratorNode (LLM, plain text) -----------------------

@log_node
def feedback_generator_node(state: ProjectAgentState) -> dict:
    passed = state["passed"]
    feedback_text = call_text(
        system=prompts.feedback_generator_prompt(state, config.PASS_THRESHOLD, passed),
        user="Write the feedback message now.",
    )
    if not passed:
        # The model's feedback is the readable summary; the specifics of what is
        # missing (requirements the code doesn't implement, absent files/folders)
        # are facts already established, so they are listed exactly, not paraphrased.
        fixes = revision.fix_list(state)
        if fixes:
            feedback_text = f"{feedback_text}\n\n### What to fix before you resubmit\n{revision.as_bullets(fixes)}"

    # Passing a content grade is final. Failing one is not — the feedback we
    # just generated explicitly tells the student what to fix "to pass on
    # resubmission" (see feedback_generator_prompt), so the system needs to
    # actually honor that and let them try again, same as a packaging-only
    # revision. Only a genuine pass closes the assignment out.
    submission_status = SubmissionStatus.graded if passed else SubmissionStatus.needs_revision
    assignment_status = AssignmentStatus.graded if passed else AssignmentStatus.needs_revision
    result_status = "graded" if passed else "needs_revision"
    review_markdown = build_review_markdown({**state, "status": result_status, "revision_notes": None if passed else feedback_text})

    session = get_session()
    try:
        submission = session.get(Submission, state["submission_id"])
        if submission:
            submission.status = submission_status
            submission.score_json = {
                "final_score": state["final_score"],
                "passed": passed,
                "score_reasoning": state.get("score_reasoning"),
                "output_verification": state.get("output_verification"),
                "code_quality_score": state.get("code_quality_score"),
                "structure_score": state.get("structure_score"),
                "zip_structure_score": state.get("zip_structure_score"),
                # Kept for the final project report (app/reports/final_report.py).
                "syntax_report": {key: (state.get("syntax_report") or {}).get(key)
                                  for key in ("checked_files", "checked_languages", "error_count")},
                "screenshot_evidence": {"valid_files": (state.get("screenshot_evidence") or {}).get("valid_files") or []},
                "submitted_files": list(state.get("zip_file_tree") or [])[:300],
            }
            submission.feedback_text = feedback_text
            submission.review_markdown = review_markdown
            session.commit()
        assignment = session.get(ProjectAssignment, state["assignment_id"])
        if assignment:
            assignment.status = assignment_status
            session.commit()
    finally:
        session.close()

    return {
        "feedback": feedback_text,
        "status": result_status,
        "revision_notes": None if passed else feedback_text,
        "final_score": state["final_score"],
        "passed": passed,
        "review_markdown": review_markdown,
    }
