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
    Certificate,
    Enrollment,
    ProjectAssignment,
    Submission,
    SubmissionStatus,
)
from app.execution.browser_check import BrowserCheckUnavailable, run_html_submission
from app.execution.entry_point import find_html_entry_point, find_node_entry_point, find_python_entry_point
from app.execution.judge0_client import Judge0Unavailable, run_node_submission, run_python_submission
from app.graph import prompts
from app.graph.state import ProjectAgentState
from app.ingestion.docx_ingest import DocxIngestError, ingest_docx
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


# --- Node 1: EligibilityCheckNode (facts from DB, verdict decided by the LLM) ---

@log_node
def eligibility_check_node(state: ProjectAgentState) -> dict:
    """The DB query below is fact retrieval, not a decision — the LLM has no
    other way to learn enrollment/certificate status. The eligibility verdict
    itself (and the message the student reads) is the LLM's call, applying the
    stated rule to those facts."""
    if state.get("skip_certificate_check"):
        return {
            "eligible": True,
            "eligibility_reason": "No certificate required — generating project options for your requested topic.",
        }

    session = get_session()
    try:
        enrollment = (
            session.query(Enrollment)
            .filter_by(student_id=state["student_id"], course_id=state["course_id"])
            .first()
        )
        certificate = (
            session.query(Certificate)
            .filter_by(student_id=state["student_id"], course_id=state["course_id"])
            .first()
        )
        facts = {
            "student_name": state["student_name"],
            "course_name": state["course_name"],
            "enrollment_exists": enrollment is not None,
            "enrollment_status": enrollment.status.value if enrollment else "none",
            "certificate_exists": certificate is not None,
        }
    finally:
        session.close()

    result = call_json(
        system=prompts.eligibility_decision_prompt(facts),
        user="Decide eligibility now.",
    )
    return {
        "eligible": bool(result.get("eligible", False)),
        "eligibility_reason": result.get("eligibility_reason", ""),
    }


@log_node
def blocked_exit_node(state: ProjectAgentState) -> dict:
    return {"status": "blocked", "feedback": state.get("eligibility_reason", "Not eligible.")}


# --- Node 2: TopicGeneratorNode (LLM) ---------------------------------------

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
    return {"submission_guide": result}


# --- Node 6: DocxIngestNode (deterministic) ---------------------------------

@log_node
def docx_ingest_node(state: ProjectAgentState) -> dict:
    try:
        parsed = ingest_docx(state["docx_path"])
    except DocxIngestError as exc:
        return {"status": "error", "feedback": str(exc)}
    return {
        "doc_sections": parsed["sections"],
        "screenshots_present": parsed["screenshots_present"],
        "screenshot_ocr_text": parsed["screenshot_ocr_text"],
    }


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
    }


# --- Node 8: StructureValidationNode (LLM) ----------------------------------

@log_node
def structure_validation_node(state: ProjectAgentState) -> dict:
    result = call_json(
        system=prompts.structure_validation_prompt(state),
        user="Validate the document structure now.",
        temperature=_SCORING_TEMPERATURE,
    )
    return {"structure_score": result}


# --- Node 9: ZipStructureValidationNode (LLM) -------------------------------

@log_node
def zip_structure_validation_node(state: ProjectAgentState) -> dict:
    result = call_json(
        system=prompts.zip_structure_validation_prompt(state),
        user="Validate the zip folder structure now.",
        temperature=_SCORING_TEMPERATURE,
    )
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
    notes: list[str] = []
    if not structure.get("is_complete", True):
        notes.append(f"Report: {structure.get('notes', 'Missing required sections.')}")
    if not zip_structure.get("is_complete", True):
        notes.append(f"Code zip: {zip_structure.get('notes', 'Folder structure incomplete.')}")
    revision_notes = "\n".join(notes) or "Submission is incomplete — see validation notes."

    session = get_session()
    try:
        submission = session.get(Submission, state["submission_id"])
        if submission:
            submission.status = SubmissionStatus.needs_revision
            submission.docx_validation_json = structure
            submission.zip_validation_json = zip_structure
            session.commit()
    finally:
        session.close()

    return {"status": "needs_revision", "revision_notes": revision_notes}


# --- Node 10: OutputVerificationNode (LLM, OCR-based) -----------------------

@log_node
def output_verification_node(state: ProjectAgentState) -> dict:
    result = call_json(
        system=prompts.output_verification_prompt(state),
        user="Verify the output evidence now.",
        temperature=_SCORING_TEMPERATURE,
    )
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
    return {
        "final_score": float(result.get("final_score", 0)),
        "passed": bool(result.get("passed", False)),
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

    # Passing a content grade is final. Failing one is not — the feedback we
    # just generated explicitly tells the student what to fix "to pass on
    # resubmission" (see feedback_generator_prompt), so the system needs to
    # actually honor that and let them try again, same as a packaging-only
    # revision. Only a genuine pass closes the assignment out.
    submission_status = SubmissionStatus.graded if passed else SubmissionStatus.needs_revision
    assignment_status = AssignmentStatus.graded if passed else AssignmentStatus.needs_revision
    result_status = "graded" if passed else "needs_revision"

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
            }
            submission.feedback_text = feedback_text
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
    }
