import base64
import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, File, Form, Header, HTTPException, Query, Request, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy import func
from starlette.concurrency import run_in_threadpool

logger = logging.getLogger("capstone.api")


def _log_id(thread_id: str) -> str:
    """Short, non-reversible stand-in for a raw thread_id in log output only
    — actual session/state lookups always use the real thread_id."""
    return hashlib.sha256(thread_id.encode()).hexdigest()[:8]

from app import config
from app.agentic.qa_agent import ProjectNotFound, ask_project_question
from app.api.schemas import (
    ConfigOut,
    CourseOut,
    EligibleCoursesResponse,
    EligibilityCheckRequest,
    EligibilityCheckResponse,
    FreeTopicRequest,
    QAAskResponse,
    StatusResponse,
    StructureScreenshotResponse,
    SubmissionResultResponse,
    TimerConfirmRequest,
    TimerConfirmResponse,
    TopicChooseRequest,
    TopicChooseResponse,
    TopicClarifyRequest,
    TopicClarifyResponse,
    UsageSummaryResponse,
    VivaAnswerRequest,
    VivaQuestionOut,
)
from app.viva import VIVA_PASS_THRESHOLD, generate_viva_questions, verify_viva_answer
from app.db.database import get_session
from app.db.models import (
    AssignmentStatus,
    Certificate,
    Course,
    CourseMedium,
    Enrollment,
    EnrollmentStatus,
    LlmUsage,
    ProjectAssignment,
    Student,
    Submission,
    SubmissionStatus,
)
from app.graph import prompts
from app.graph.graph import compiled_graph, submission_graph
from app.ingestion.docx_ingest import DocxIngestError, ingest_docx
from app.llm.client import LLMError, call_json, call_text
from app.vision.structure_screenshot import analyze_structure_screenshot

router = APIRouter(prefix="/api")


@router.get("/eligibility/courses", response_model=EligibleCoursesResponse)
def eligible_courses(phone: str = Query(min_length=1)) -> EligibleCoursesResponse:
    """Return only completed courses with an issued certificate for this mobile number."""
    session = get_session()
    try:
        student = session.query(Student).filter_by(phone=phone).first()
        if student is None:
            return EligibleCoursesResponse(student_found=False, courses=[])

        courses = (
            session.query(Course)
            .join(Enrollment, Enrollment.course_id == Course.id)
            .join(
                Certificate,
                (Certificate.course_id == Course.id) & (Certificate.student_id == student.id),
            )
            .filter(
                Enrollment.student_id == student.id,
                Enrollment.status == EnrollmentStatus.completed,
            )
            .distinct()
            .order_by(Course.name)
            .all()
        )
        return EligibleCoursesResponse(
            student_found=True,
            courses=[CourseOut(id=c.id, name=c.name, medium=c.medium.value) for c in courses],
        )
    finally:
        session.close()


@router.get("/courses", response_model=list[CourseOut])
def list_courses() -> list[CourseOut]:
    session = get_session()
    try:
        courses = session.query(Course).order_by(Course.name).all()
        return [CourseOut(id=c.id, name=c.name, medium=c.medium.value) for c in courses]
    finally:
        session.close()


@router.get("/config", response_model=ConfigOut)
def get_config() -> ConfigOut:
    return ConfigOut(
        pass_threshold=config.PASS_THRESHOLD,
        submission_window_days=config.SUBMISSION_WINDOW_DAYS,
        max_upload_mb=config.MAX_UPLOAD_MB,
    )


def usage_summary(user_id: str | None) -> UsageSummaryResponse:
    """Token usage for this agent, scoped to the verified DigiDARA identity
    (`X-DigiDARA-User-Id`, forwarded by the orchestrator gateway) that made
    the calls. Without a verified identity there is nothing safe to
    attribute the request to, so this returns all-zero totals rather than
    a platform-wide aggregate. Backs the Settings > Usage dashboard."""
    session = get_session()
    try:
        base = (
            session.query(LlmUsage).filter(LlmUsage.user_id == user_id)
            if user_id
            else session.query(LlmUsage).filter(LlmUsage.id.is_(None))
        )
        total_requests, total_tokens, prompt_tokens, completion_tokens = base.with_entities(
            func.count(LlmUsage.id),
            func.coalesce(func.sum(LlmUsage.total_tokens), 0),
            func.coalesce(func.sum(LlmUsage.prompt_tokens), 0),
            func.coalesce(func.sum(LlmUsage.completion_tokens), 0),
        ).one()
        by_type = dict(
            base.with_entities(LlmUsage.request_type, func.coalesce(func.sum(LlmUsage.total_tokens), 0))
            .group_by(LlmUsage.request_type)
            .all()
        )
    finally:
        session.close()
    return UsageSummaryResponse(
        agent_name="capstone_project_agent",
        total_requests=total_requests,
        total_tokens=int(total_tokens),
        prompt_tokens=int(prompt_tokens),
        completion_tokens=int(completion_tokens),
        by_request_type={k: int(v) for k, v in by_type.items()},
    )


@router.get("/usage/summary", response_model=UsageSummaryResponse)
def usage_summary_route(
    x_digidara_user_id: str | None = Header(None, alias="X-DigiDARA-User-Id"),
) -> UsageSummaryResponse:
    return usage_summary(x_digidara_user_id)


def _thread_config(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}


def _get_state_values(thread_id: str) -> dict:
    snapshot = compiled_graph.get_state(_thread_config(thread_id))
    if snapshot is None or not snapshot.values:
        raise HTTPException(404, "Unknown or expired thread_id.")
    return snapshot.values


def _invoke_graph(update: dict | None, thread_id: str) -> dict:
    """Runs the graph and turns any failure (most commonly: the configured
    LLM provider being unreachable or misconfigured) into a clean 502 instead
    of leaking a raw traceback to the client.

    Resuming a thread that's paused at an `interrupt_before` node needs two
    steps, not one: `invoke(update, config)` merges `update` into the paused
    checkpoint but does NOT execute past the interrupt in that same call — a
    second `invoke(None, config)` is what actually runs the next node. For a
    brand-new thread (no checkpoint yet) there's nothing to resume, so the
    update *is* the initial state and a single invoke is correct.
    """
    cfg = _thread_config(thread_id)
    try:
        existing = compiled_graph.get_state(cfg)
        if update and existing is not None and existing.values:
            compiled_graph.update_state(cfg, update)
            return compiled_graph.invoke(None, cfg)
        return compiled_graph.invoke(update, cfg)
    except HTTPException:
        raise
    except LLMError as exc:
        logger.warning("Graph execution rate-limited for thread_id=%s: %s", _log_id(thread_id), exc)
        raise HTTPException(502, f"{exc} Your progress up to this point is saved.")
    except Exception:
        logger.exception("Graph execution failed for thread_id=%s", _log_id(thread_id))
        raise HTTPException(
            502,
            "The AI service could not complete this step (check LLM_MODEL / API key configuration). "
            "Your progress up to this point is saved — retry once the provider is reachable.",
        )


def _run_submission(sub_state: dict) -> dict:
    """Every submit/resubmit is a fresh, checkpoint-free run of the submission
    graph (see graph.py docstring for why this isn't a resumed continuation
    of the main thread). Same clean-502-on-failure behavior as `_invoke_graph`."""
    try:
        return submission_graph.invoke(sub_state)
    except LLMError as exc:
        logger.warning("Submission graph execution rate-limited: %s", exc)
        raise HTTPException(502, f"{exc} Your progress up to this point is saved.")
    except Exception:
        logger.exception("Submission graph execution failed")
        raise HTTPException(
            502,
            "The AI service could not complete this step (check LLM_MODEL / API key configuration). "
            "Your progress up to this point is saved — retry once the provider is reachable.",
        )


@router.post("/eligibility/check", response_model=EligibilityCheckResponse)
def eligibility_check(req: EligibilityCheckRequest) -> EligibilityCheckResponse:
    logger.info("=== POST /api/eligibility/check name=%r phone=%r course=%r", req.name, req.phone, req.course_name)
    session = get_session()
    try:
        student = session.query(Student).filter_by(phone=req.phone).first()
        if student is None:
            student = Student(name=req.name, email=req.email, phone=req.phone)
            session.add(student)
            session.flush()
        elif req.email and student.email != req.email:
            student.email = req.email

        course = session.query(Course).filter_by(name=req.course_name).first()
        if course is None:
            raise HTTPException(404, f"Unknown course: {req.course_name!r}")

        assignment = ProjectAssignment(
            student_id=student.id,
            course_id=course.id,
            medium=course.medium,
            status=AssignmentStatus.awaiting_topic_choice,
        )
        session.add(assignment)
        session.commit()

        thread_id = assignment.thread_id
        initial_state = {
            "student_id": student.id,
            "course_id": course.id,
            "assignment_id": assignment.id,
            "student_name": student.name,
            "phone": student.phone,
            "course_name": course.name,
            "course_medium": course.medium.value,
        }
    finally:
        session.close()

    result = _invoke_graph(initial_state, thread_id)

    logger.info(
        "=== eligibility=%s thread=%s reason=%r",
        result.get("eligible"), _log_id(thread_id), result.get("eligibility_reason"),
    )
    return EligibilityCheckResponse(
        thread_id=thread_id,
        eligible=result.get("eligible", False),
        eligibility_reason=result.get("eligibility_reason", ""),
        topic_options=result.get("topic_options"),
    )


@router.post("/topic/clarify", response_model=TopicClarifyResponse)
def topic_clarify(req: TopicClarifyRequest) -> TopicClarifyResponse:
    """Stateless pre-check for a free-topic request — deliberately not part
    of the LangGraph (no thread/state needed): decides whether the
    student's free text already has enough specificity (company/role/stack)
    to generate two well-targeted topics, or whether the frontend should
    show one clarifying question first and re-call /eligibility/free with
    the combined answer. See prompts.topic_clarification_prompt."""
    logger.info("=== POST /api/topic/clarify description=%r", req.description)
    result = call_json(
        system=prompts.topic_clarification_prompt(req.description),
        user="Decide now.",
        temperature=0.3,
    )
    ready = bool(result.get("ready", True))
    return TopicClarifyResponse(
        ready=ready,
        clarifying_question=result.get("clarifying_question") if not ready else None,
    )


@router.post("/eligibility/free", response_model=EligibilityCheckResponse)
def eligibility_check_free(req: FreeTopicRequest) -> EligibilityCheckResponse:
    """Skip the certificate gate entirely: generate project topics for any
    language, role, or topic the student names. `req.course_name` doubles as
    that free-text topic here. A `Course` row is looked up or created for it
    (medium defaults to `local`) purely so course_id-keyed tables/queries
    downstream (ProjectAssignment, topic_generator_node's past-topic dedup)
    keep working unchanged; eligibility_check_node skips its enrollment/
    certificate DB check via the skip_certificate_check state flag below."""
    logger.info(
        "=== POST /api/eligibility/free name=%r phone=%r topic=%r difficulty=%r",
        req.name, req.phone, req.course_name, req.difficulty,
    )
    email = req.email.strip().lower()

    session = get_session()
    try:
        # Keyed on email, not phone — this flow has no enrollment records to
        # match a phone against (that's what eligibility_check/eligible_courses
        # use it for), and a logged-in account's email is always present,
        # unlike an optionally-blank phone (e.g. Google sign-in).
        student = session.query(Student).filter_by(email=email).first()
        if student is None:
            student = Student(name=req.name, email=email, phone=req.phone or None)
            session.add(student)
            session.flush()
        else:
            if req.name and student.name != req.name:
                student.name = req.name
            if req.phone and student.phone != req.phone:
                student.phone = req.phone

        # Course.name is a DB column capped at 255 chars — it's only ever
        # used as a dedup/lookup key here (topic_generator_node's past-topic
        # avoidance groups by course_id), never shown to the student or the
        # LLM directly, so truncating it for storage is safe. The full,
        # untruncated req.course_name is what actually reaches the LLM via
        # state["course_name"] below — truncating *that* would silently
        # drop real content (e.g. the second half of a clarification-answer
        # combination) for no benefit.
        course_db_name = req.course_name[:255]
        course = session.query(Course).filter_by(name=course_db_name).first()
        if course is None:
            course = Course(name=course_db_name, medium=CourseMedium.local)
            session.add(course)
            session.flush()

        assignment = ProjectAssignment(
            student_id=student.id,
            course_id=course.id,
            medium=course.medium,
            status=AssignmentStatus.awaiting_topic_choice,
        )
        session.add(assignment)
        session.commit()

        thread_id = assignment.thread_id
        initial_state = {
            "student_id": student.id,
            "course_id": course.id,
            "assignment_id": assignment.id,
            "student_name": student.name,
            "phone": student.phone or "",
            "course_name": req.course_name,
            "course_medium": course.medium.value,
            "skip_certificate_check": True,
            "free_topic_request": True,
            "difficulty": req.difficulty,
        }
    finally:
        session.close()

    result = _invoke_graph(initial_state, thread_id)

    logger.info(
        "=== free-topic eligibility=%s thread=%s reason=%r",
        result.get("eligible"), _log_id(thread_id), result.get("eligibility_reason"),
    )
    return EligibilityCheckResponse(
        thread_id=thread_id,
        eligible=result.get("eligible", False),
        eligibility_reason=result.get("eligibility_reason", ""),
        topic_options=result.get("topic_options"),
    )


@router.post("/topic/choose", response_model=TopicChooseResponse)
def topic_choose(req: TopicChooseRequest) -> TopicChooseResponse:
    logger.info("=== POST /api/topic/choose thread=%s topic_id=%s", _log_id(req.thread_id), req.topic_id)
    state = _get_state_values(req.thread_id)
    options = state.get("topic_options", [])
    chosen = next((opt for opt in options if opt.get("id") == req.topic_id), None)
    if chosen is None:
        raise HTTPException(400, f"topic_id {req.topic_id!r} does not match a generated option.")

    result = _invoke_graph({"chosen_topic": chosen}, req.thread_id)

    return TopicChooseResponse(
        thread_id=req.thread_id,
        chosen_topic=result["chosen_topic"],
        requirements=result["requirements"],
    )


@router.post("/timer/confirm", response_model=TimerConfirmResponse)
def timer_confirm(req: TimerConfirmRequest) -> TimerConfirmResponse:
    logger.info("=== POST /api/timer/confirm thread=%s", _log_id(req.thread_id))
    result = _invoke_graph(None, req.thread_id)
    return TimerConfirmResponse(
        thread_id=req.thread_id,
        deadline_at=result["deadline_at"],
        submission_guide=result["submission_guide"],
        about_markdown=result.get("about_markdown"),
    )


@router.post("/submission/upload", response_model=SubmissionResultResponse)
async def submission_upload(
    thread_id: str = Form(...),
    docx_file: UploadFile = File(...),
    zip_file: UploadFile = File(...),
) -> SubmissionResultResponse:
    logger.info(
        "=== POST /api/submission/upload thread=%s docx=%r (%d bytes) zip=%r (%d bytes)",
        _log_id(thread_id), docx_file.filename, docx_file.size or -1, zip_file.filename, zip_file.size or -1,
    )
    state = _get_state_values(thread_id)
    assignment_id = state["assignment_id"]

    if state.get("status") == "graded":
        raise HTTPException(409, "This assignment has already been graded and cannot be resubmitted.")

    if not docx_file.filename.lower().endswith(".docx"):
        raise HTTPException(400, "The report must be a .docx file.")
    if not zip_file.filename.lower().endswith(".zip"):
        raise HTTPException(400, "The source code archive must be a .zip file.")

    docx_bytes = await docx_file.read()
    zip_bytes = await zip_file.read()
    if not docx_bytes or not zip_bytes:
        raise HTTPException(400, "Both the report and the source zip must be non-empty.")
    if len(docx_bytes) > config.MAX_UPLOAD_BYTES or len(zip_bytes) > config.MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"Uploaded files must each be under {config.MAX_UPLOAD_BYTES // (1024*1024)} MB.")

    session = get_session()
    try:
        assignment = session.get(ProjectAssignment, assignment_id)
        if assignment is None:
            raise HTTPException(404, "Assignment not found.")
        deadline = assignment.deadline_at
        if deadline is not None:
            # SQLite doesn't persist tzinfo on DateTime(timezone=True) columns —
            # values we wrote as UTC-aware come back naive. We only ever store
            # UTC here, so a naive value read back is safe to treat as UTC.
            if deadline.tzinfo is None:
                deadline = deadline.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) > deadline:
                raise HTTPException(410, "The 7-day submission window has closed.")

        submission_dir = config.UPLOAD_DIR / thread_id
        submission_dir.mkdir(parents=True, exist_ok=True)
        docx_path = submission_dir / f"report_{uuid.uuid4().hex[:8]}.docx"
        zip_path = submission_dir / f"source_{uuid.uuid4().hex[:8]}.zip"
        docx_path.write_bytes(docx_bytes)
        zip_path.write_bytes(zip_bytes)

        submission = Submission(
            assignment_id=assignment_id,
            docx_path=str(docx_path),
            zip_path=str(zip_path),
            status=SubmissionStatus.processing,
        )
        session.add(submission)
        assignment.status = AssignmentStatus.submitted
        session.commit()
        submission_id = submission.id
    finally:
        session.close()

    sub_state = {
        "submission_id": submission_id,
        "docx_path": str(docx_path),
        "zip_path": str(zip_path),
        "assignment_id": assignment_id,
        "student_name": state["student_name"],
        "course_medium": state["course_medium"],
        "chosen_topic": state["chosen_topic"],
        "requirements": state["requirements"],
        "submission_guide": state["submission_guide"],
    }
    result = _run_submission(sub_state)
    logger.info(
        "=== submission result thread=%s status=%s final_score=%s passed=%s",
        _log_id(thread_id), result.get("status"), result.get("final_score"), result.get("passed"),
    )

    if result.get("status") == "error":
        compiled_graph.update_state(_thread_config(thread_id), {"status": "error"})
        raise HTTPException(422, result.get("feedback", "Submission could not be processed."))

    if result.get("status") == "needs_revision":
        compiled_graph.update_state(
            _thread_config(thread_id),
            {
                "status": result.get("status"),
                "revision_notes": result.get("revision_notes"),
                "final_score": result.get("final_score"),
                "passed": result.get("passed"),
                "feedback": result.get("feedback"),
                "score_reasoning": result.get("score_reasoning"),
                "code_quality_score": result.get("code_quality_score"),
                "review_markdown": result.get("review_markdown"),
            },
        )
        return SubmissionResultResponse(
            thread_id=thread_id,
            status="needs_revision",
            submission_id=submission_id,
            revision_notes=result.get("revision_notes"),
            # Present when this was a failed *content* grade being sent back
            # for another attempt (not just a packaging/structure issue) —
            # absent for a plain structure-gate rejection.
            final_score=result.get("final_score"),
            passed=result.get("passed"),
            score_reasoning=result.get("score_reasoning"),
            code_quality_score=result.get("code_quality_score"),
            review_markdown=result.get("review_markdown"),
        )

    # Content grade passed -- hold the score back and run the viva before
    # revealing it. See app/viva.py.
    questions = generate_viva_questions(
        state["chosen_topic"], state["course_medium"], result.get("zip_code_files") or {}
    )
    session = get_session()
    try:
        submission = session.get(Submission, submission_id)
        if submission is None:
            raise HTTPException(404, "Submission not found.")
        submission.viva_questions_json = questions
        submission.viva_answers_json = []
        submission.status = SubmissionStatus.pending_viva
        submission.score_json = {
            "final_score": result.get("final_score"),
            "passed": result.get("passed"),
            "feedback": result.get("feedback"),
            "score_reasoning": result.get("score_reasoning"),
            "code_quality_score": result.get("code_quality_score"),
        }
        session.commit()
    finally:
        session.close()

    compiled_graph.update_state(_thread_config(thread_id), {"status": "pending_viva"})

    first_question = questions[0] if questions else None
    return SubmissionResultResponse(
        thread_id=thread_id,
        status="pending_viva",
        submission_id=submission_id,
        viva_question=VivaQuestionOut(**first_question) if first_question else None,
        viva_progress=f"1 of {len(questions)}" if questions else None,
    )


def submit_viva_answer(req: VivaAnswerRequest) -> SubmissionResultResponse:
    logger.info("=== POST /api/viva/answer submission=%s question=%s", req.submission_id, req.question_id)
    session = get_session()
    try:
        submission = session.get(Submission, req.submission_id)
        if submission is None:
            raise HTTPException(404, "Submission not found.")
        if submission.status != SubmissionStatus.pending_viva:
            raise HTTPException(409, "This submission is not awaiting a viva answer.")

        thread_id = submission.assignment.thread_id
        questions = submission.viva_questions_json or []
        answers = submission.viva_answers_json or []
        expected_index = len(answers)
        if req.question_id != expected_index:
            raise HTTPException(409, f"Expected an answer for question {expected_index}, got {req.question_id}.")

        question = next((q for q in questions if q["id"] == req.question_id), None)
        if question is None:
            raise HTTPException(404, "Unknown viva question.")

        verdict = verify_viva_answer(question["question"], question.get("expected_concepts", []), req.answer)
        answers = answers + [{
            "question_id": req.question_id,
            "answer": req.answer,
            "correct": verdict["correct"],
            "note": verdict["note"],
        }]
        submission.viva_answers_json = answers

        if len(answers) < len(questions):
            session.commit()
            next_question = questions[len(answers)]
            return SubmissionResultResponse(
                thread_id=thread_id,
                status="pending_viva",
                submission_id=req.submission_id,
                viva_question=VivaQuestionOut(**next_question),
                viva_progress=f"{len(answers) + 1} of {len(questions)}",
            )

        # Last question just answered -- finalize both scores together.
        correct_count = sum(1 for a in answers if a["correct"])
        viva_passed = correct_count >= VIVA_PASS_THRESHOLD
        submission.viva_score = float(correct_count)
        submission.viva_passed = viva_passed

        code_result = submission.score_json or {}
        code_passed = bool(code_result.get("passed"))
        overall_passed = code_passed and viva_passed

        final_status = SubmissionStatus.graded if overall_passed else SubmissionStatus.needs_revision
        submission.status = final_status
        session.commit()

        viva_note = (
            f"\n\nViva result: {correct_count} of {len(questions)} correct "
            f"({'passed' if viva_passed else 'not enough correct answers to pass'})."
        )
        combined_feedback = (code_result.get("feedback") or "") + viva_note

        compiled_graph.update_state(
            _thread_config(thread_id),
            {
                "status": final_status.value,
                "final_score": code_result.get("final_score"),
                "passed": overall_passed,
                "feedback": combined_feedback,
                "score_reasoning": code_result.get("score_reasoning"),
                "code_quality_score": code_result.get("code_quality_score"),
                "review_markdown": submission.review_markdown,
            },
        )

        return SubmissionResultResponse(
            thread_id=thread_id,
            status=final_status.value,
            submission_id=req.submission_id,
            final_score=code_result.get("final_score"),
            passed=overall_passed,
            feedback=combined_feedback,
            score_reasoning=code_result.get("score_reasoning"),
            code_quality_score=code_result.get("code_quality_score"),
            review_markdown=submission.review_markdown,
            viva_score=submission.viva_score,
            viva_passed=viva_passed,
        )
    finally:
        session.close()


@router.get("/status/{thread_id}", response_model=StatusResponse)
def get_status(thread_id: str) -> StatusResponse:
    logger.debug("=== GET /api/status/%s", _log_id(thread_id))
    snapshot = compiled_graph.get_state(_thread_config(thread_id))
    if snapshot is None or not snapshot.values:
        raise HTTPException(404, "Unknown or expired thread_id.")

    values = snapshot.values
    next_nodes = snapshot.next
    step_map = {
        "requirement_expansion": "awaiting_topic_choice",
        "timer_init": "awaiting_timer_confirmation",
    }
    if next_nodes:
        next_step = step_map.get(next_nodes[0], next_nodes[0])
    elif values.get("status"):
        # A submission has run (needs_revision/graded/error) — the top-level
        # `status` field is the authoritative signal here.
        next_step = values["status"]
    elif values.get("submission_guide") is not None:
        # Main graph finished at generate_submission_guide -> END; the
        # submission graph (a separate, checkpoint-free run) hasn't reported
        # an outcome back yet.
        next_step = "awaiting_submission_upload"
    else:
        next_step = "done"
    return StatusResponse(
        thread_id=thread_id,
        status=values.get("status"),
        deadline_at=values.get("deadline_at"),
        next_step=next_step,
        eligible=values.get("eligible"),
        eligibility_reason=values.get("eligibility_reason"),
        topic_options=values.get("topic_options"),
        chosen_topic=values.get("chosen_topic"),
        requirements=values.get("requirements"),
        submission_guide=values.get("submission_guide"),
        about_markdown=values.get("about_markdown"),
        final_score=values.get("final_score"),
        passed=values.get("passed"),
        feedback=values.get("feedback"),
        revision_notes=values.get("revision_notes"),
        score_reasoning=values.get("score_reasoning"),
        code_quality_score=values.get("code_quality_score"),
        review_markdown=values.get("review_markdown"),
    )


@router.get("/assignment/{thread_id}/about.md")
def get_about_markdown(thread_id: str) -> PlainTextResponse:
    """Downloadable "about this project" doc -- topic, requirements, and the
    required folder/report structure -- generated once the submission guide
    is ready. Useful as a reference while building, and to bring to the viva."""
    values = _get_state_values(thread_id)
    markdown = values.get("about_markdown")
    if not markdown:
        raise HTTPException(404, "No project brief has been generated yet for this thread.")
    return PlainTextResponse(markdown, media_type="text/markdown")


@router.get("/submission/{submission_id}/review.md")
def get_review_markdown(submission_id: str) -> PlainTextResponse:
    """Downloadable full review report for one submission attempt -- see
    app/graph/report.py:build_review_markdown. Available as soon as a
    submission attempt finishes (including a structure-gate rejection),
    regardless of whether the content score itself is still held back
    pending the viva."""
    session = get_session()
    try:
        submission = session.get(Submission, submission_id)
    finally:
        session.close()
    if submission is None:
        raise HTTPException(404, "Submission not found.")
    if not submission.review_markdown:
        raise HTTPException(404, "No review report is available for this submission yet.")
    return PlainTextResponse(submission.review_markdown, media_type="text/markdown")


@router.post("/submission/{submission_id}/structure-screenshot", response_model=StructureScreenshotResponse)
async def structure_screenshot(submission_id: str, image: UploadFile = File(...)) -> StructureScreenshotResponse:
    """Phase 3: a student confused by a "missing folder" verdict attaches a
    screenshot of their file explorer / extracted zip / IDE tree, and a
    vision-capable LLM call points at exactly what's missing from THAT
    screenshot -- grounded in the same deterministic missing-items list the
    review report already used (see app/ingestion/structure_check.py)."""
    logger.info("=== POST /api/submission/%s/structure-screenshot", submission_id)
    session = get_session()
    try:
        submission = session.get(Submission, submission_id)
    finally:
        session.close()
    if submission is None:
        raise HTTPException(404, "Submission not found.")

    zip_score = submission.zip_validation_json or (submission.score_json or {}).get("zip_structure_score") or {}
    detail = zip_score.get("required_paths_detail") or {}
    missing_items = detail.get("missing_items") or []
    if not missing_items:
        raise HTTPException(400, "This submission has no missing required folders/files to check a screenshot against.")

    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(400, "Please attach an image file (a screenshot).")
    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(400, "The screenshot is empty.")
    if len(image_bytes) > config.MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"Screenshot must be under {config.MAX_UPLOAD_BYTES // (1024*1024)} MB.")

    result = analyze_structure_screenshot(image_bytes, image.content_type, missing_items, detail.get("matched_items") or [])
    return StructureScreenshotResponse(**result)


@router.post("/qa/ask", response_model=QAAskResponse)
async def qa_ask(
    thread_id: str = Form(...),
    question: str = Form(...),
    attachment: UploadFile | None = File(None),
) -> QAAskResponse:
    """Phase 4: project-scoped Q&A. Answers are grounded ONLY in this
    student's own topic/requirements/submitted code/report/grading result
    (see app/agentic/qa_agent.py) -- the agent decides which of those to
    look at via real tool calls, using web search only to verify a
    technical claim or a current requirement. An optional image or .docx
    attachment is analyzed and folded into that single question's context;
    it is not persisted."""
    logger.info("=== POST /api/qa/ask thread=%s", _log_id(thread_id))
    if not question.strip():
        raise HTTPException(400, "Question must not be empty.")

    extra_context: str | None = None
    if attachment is not None:
        attachment_bytes = await attachment.read()
        if not attachment_bytes:
            raise HTTPException(400, "The attachment is empty.")
        if len(attachment_bytes) > config.MAX_UPLOAD_BYTES:
            raise HTTPException(413, f"Attachment must be under {config.MAX_UPLOAD_BYTES // (1024*1024)} MB.")

        content_type = attachment.content_type or ""
        filename = (attachment.filename or "").lower()
        if content_type.startswith("image/"):
            data_url = f"data:{content_type};base64,{base64.b64encode(attachment_bytes).decode('ascii')}"
            description = call_text(
                system="Describe what is shown in this image in plain language, in under 150 words. "
                "If it looks like a file explorer, archive tool, or code editor file tree, list the "
                "folder/file names you can actually read in it.",
                user="Describe the attached image now.",
                image_data_url=data_url,
            )
            extra_context = f"[Image attached by the student]\n{description}"
        elif filename.endswith(".docx"):
            tmp_dir = config.UPLOAD_DIR / "qa_attachments"
            tmp_dir.mkdir(parents=True, exist_ok=True)
            tmp_path = tmp_dir / f"{uuid.uuid4().hex}.docx"
            tmp_path.write_bytes(attachment_bytes)
            try:
                parsed = ingest_docx(str(tmp_path))
            except DocxIngestError as exc:
                raise HTTPException(400, str(exc))
            finally:
                tmp_path.unlink(missing_ok=True)
            sections_text = json.dumps(parsed["sections"], ensure_ascii=False)
            if len(sections_text) > 6000:
                sections_text = sections_text[:6000] + "... [truncated]"
            extra_context = f"[.docx document attached by the student]\n{sections_text}"
        elif filename.endswith(".pdf"):
            raise HTTPException(415, "PDF attachments aren't supported yet — please attach a .docx report or an image screenshot instead.")
        else:
            raise HTTPException(415, "Unsupported attachment type — please attach a .docx report or an image screenshot.")

    try:
        result = ask_project_question(thread_id, question, extra_context=extra_context)
    except ProjectNotFound:
        raise HTTPException(404, "Unknown or expired thread_id.")
    except LLMError as exc:
        raise HTTPException(502, f"{exc}")
    return QAAskResponse(answer=result["answer"], tools_used=result["tools_used"])


@router.post("/invoke")
async def invoke(request: Request) -> JSONResponse:
    """Common Strategy F contract used by the registry-resolved gateway."""
    content_type = request.headers.get("content-type", "")
    if content_type.startswith("multipart/form-data"):
        form = await request.form()
        action = str(form.get("action", ""))
        if action != "upload_submission":
            raise HTTPException(400, "Multipart requests only support upload_submission.")
        thread_id = str(form.get("thread_id", ""))
        docx_file = form.get("docx_file")
        zip_file = form.get("zip_file")
        if not thread_id or not hasattr(docx_file, "read") or not hasattr(zip_file, "read"):
            raise HTTPException(400, "thread_id, docx_file, and zip_file are required.")
        result = await submission_upload(thread_id=thread_id, docx_file=docx_file, zip_file=zip_file)
        return JSONResponse(content=jsonable_encoder(result))

    try:
        body = await request.json()
    except Exception as exc:
        raise HTTPException(400, "Expected a JSON or multipart request body.") from exc

    action = body.get("action")
    payload = body.get("payload") or {}
    if action == "health":
        result = {"status": "ok", "agent_name": "capstone_project_agent"}
    elif action == "eligible_courses":
        result = await run_in_threadpool(eligible_courses, str(payload.get("phone", "")))
    elif action == "clarify_topic_request":
        result = await run_in_threadpool(topic_clarify, TopicClarifyRequest(**payload))
    elif action == "check_eligibility":
        result = await run_in_threadpool(eligibility_check, EligibilityCheckRequest(**payload))
    elif action == "check_eligibility_free":
        result = await run_in_threadpool(eligibility_check_free, FreeTopicRequest(**payload))
    elif action == "choose_topic":
        result = await run_in_threadpool(topic_choose, TopicChooseRequest(**payload))
    elif action == "confirm_timer":
        result = await run_in_threadpool(timer_confirm, TimerConfirmRequest(**payload))
    elif action == "status":
        result = await run_in_threadpool(get_status, str(payload.get("thread_id", "")))
    elif action == "usage_summary":
        result = await run_in_threadpool(usage_summary, request.headers.get("x-digidara-user-id"))
    elif action == "submit_viva_answer":
        result = await run_in_threadpool(submit_viva_answer, VivaAnswerRequest(**payload))
    else:
        raise HTTPException(400, f"Unknown action: {action!r}")
    return JSONResponse(content=jsonable_encoder(result))
