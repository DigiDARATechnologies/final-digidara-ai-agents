"""Knowledge test API (see service.py). Building a test is for an
organization's admins only; learners reach a test through an assessment link."""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.auth.verified import get_verified_user_id
from app.knowledge import report_pdf, service
from app.knowledge.extract import MAX_FILE_BYTES
from app.knowledge.service import KnowledgeError
from app.organizations.service import OrgError
from app.proctoring.service import ProctorError
from app.rate_limit import limiter

router = APIRouter(tags=["knowledge"])


class TestIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    question_type: str = "mcq"
    num_questions: int = Field(default=10, ge=1, le=service.MAX_QUESTIONS)
    seconds_per_question: int = Field(default=90, ge=20, le=600)
    instructions: str = Field(default="", max_length=2000)


class TestUpdateIn(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    question_type: str | None = None
    num_questions: int | None = Field(default=None, ge=1, le=service.MAX_QUESTIONS)
    seconds_per_question: int | None = Field(default=None, ge=20, le=600)
    instructions: str | None = Field(default=None, max_length=2000)


class QuestionIn(BaseModel):
    question: str | None = Field(default=None, max_length=1000)
    options: list[str] | None = Field(default=None, max_length=4)
    correct: int | None = Field(default=None, ge=0, le=3)
    answer: str | None = Field(default=None, max_length=2000)
    explanation: str | None = Field(default=None, max_length=1000)


class AttemptIn(BaseModel):
    session_id: str = Field(min_length=1, max_length=32)


class AnswerIn(BaseModel):
    question_id: str = Field(min_length=1, max_length=32)
    answer: str = Field(default="", max_length=5000)
    time_taken: float = 0
    timed_out: bool = False


def _run(fn, *args):
    try:
        return fn(*args)
    except (KnowledgeError, OrgError, ProctorError) as exc:
        raise HTTPException(exc.status_code, exc.message) from exc


def _pdf(report: dict) -> Response:
    safe = "".join(ch if ch.isalnum() else "_" for ch in str(report.get("title", "test")))[:60] or "test"
    return Response(content=report_pdf.build(report), media_type="application/pdf",
                    headers={"content-disposition": f'attachment; filename="{safe}_report.pdf"', "cache-control": "private, no-store"})


# --- the organization's admins ------------------------------------------------

BASE = "/organizations/{org_id}/knowledge-tests"


@router.get(BASE)
def list_tests(org_id: str, user_id: str = Depends(get_verified_user_id)) -> list[dict]:
    return _run(service.list_tests, user_id, org_id)


@router.post(BASE, status_code=201)
def create_test(org_id: str, req: TestIn, user_id: str = Depends(get_verified_user_id)) -> dict:
    return _run(service.create_test, user_id, org_id, req.model_dump())


@router.get(BASE + "/{test_id}")
def get_test(org_id: str, test_id: str, user_id: str = Depends(get_verified_user_id)) -> dict:
    return _run(service.get_test, user_id, org_id, test_id)


@router.patch(BASE + "/{test_id}")
def update_test(org_id: str, test_id: str, req: TestUpdateIn, user_id: str = Depends(get_verified_user_id)) -> dict:
    return _run(service.update_test, user_id, org_id, test_id, req.model_dump(exclude_unset=True, exclude_none=True))


@router.delete(BASE + "/{test_id}", status_code=204)
def delete_test(org_id: str, test_id: str, user_id: str = Depends(get_verified_user_id)) -> Response:
    _run(service.delete_test, user_id, org_id, test_id)
    return Response(status_code=204)


@router.post(BASE + "/{test_id}/documents")
@limiter.limit("20/minute")
async def upload_documents(org_id: str, test_id: str, request: Request, files: list[UploadFile] = File(...),
                           user_id: str = Depends(get_verified_user_id)) -> dict:
    if not files:
        raise HTTPException(400, "Choose at least one file.")
    if len(files) > service.MAX_DOCUMENTS:
        raise HTTPException(400, f"Upload at most {service.MAX_DOCUMENTS} files at a time.")
    read: list[tuple[str, bytes]] = []
    for upload in files:
        data = await upload.read(MAX_FILE_BYTES + 1)
        read.append((upload.filename or "document", data))
    # Reading (and the vision model for images) blocks: run it off the event loop.
    from starlette.concurrency import run_in_threadpool

    return await run_in_threadpool(_run, service.add_documents, user_id, org_id, test_id, read)


@router.delete(BASE + "/{test_id}/documents/{document_id}")
def delete_document(org_id: str, test_id: str, document_id: str, user_id: str = Depends(get_verified_user_id)) -> dict:
    return _run(service.delete_document, user_id, org_id, test_id, document_id)


@router.post(BASE + "/{test_id}/generate", status_code=202)
@limiter.limit("10/minute")
def generate(org_id: str, test_id: str, request: Request, background: BackgroundTasks,
             user_id: str = Depends(get_verified_user_id)) -> dict:
    test = _run(service.start_generation, user_id, org_id, test_id)
    background.add_task(service.run_generation, test_id)
    return test


@router.patch(BASE + "/{test_id}/questions/{question_id}")
def update_question(org_id: str, test_id: str, question_id: str, req: QuestionIn, user_id: str = Depends(get_verified_user_id)) -> dict:
    return _run(service.update_question, user_id, org_id, test_id, question_id, req.model_dump(exclude_none=True))


@router.delete(BASE + "/{test_id}/questions/{question_id}")
def delete_question(org_id: str, test_id: str, question_id: str, user_id: str = Depends(get_verified_user_id)) -> dict:
    return _run(service.delete_question, user_id, org_id, test_id, question_id)


@router.get("/organizations/{org_id}/proctoring/{session_id}/knowledge-report")
def admin_report(org_id: str, session_id: str, user_id: str = Depends(get_verified_user_id)) -> dict:
    return _run(service.admin_report, user_id, org_id, session_id)


@router.get("/organizations/{org_id}/proctoring/{session_id}/knowledge-report.pdf")
def admin_report_pdf(org_id: str, session_id: str, user_id: str = Depends(get_verified_user_id)) -> Response:
    return _pdf(_run(service.admin_report, user_id, org_id, session_id))


# --- the learner ------------------------------------------------------------------

@router.post("/knowledge/attempts")
@limiter.limit("20/minute")
def start_attempt(req: AttemptIn, request: Request, user_id: str = Depends(get_verified_user_id)) -> dict:
    return _run(service.start_attempt, user_id, req.session_id)


@router.post("/knowledge/attempts/{attempt_id}/answers")
@limiter.limit("120/minute")
def submit_answer(attempt_id: str, req: AnswerIn, request: Request, user_id: str = Depends(get_verified_user_id)) -> dict:
    return _run(service.submit_answer, user_id, attempt_id, req.question_id, req.answer, req.time_taken, req.timed_out)


@router.post("/knowledge/attempts/{attempt_id}/finish")
@limiter.limit("10/minute")
def finish_attempt(attempt_id: str, request: Request, user_id: str = Depends(get_verified_user_id)) -> dict:
    return _run(service.finish_attempt, user_id, attempt_id)


@router.get("/knowledge/attempts/{attempt_id}/report.pdf")
def learner_report_pdf(attempt_id: str, user_id: str = Depends(get_verified_user_id)) -> Response:
    return _pdf(_run(service.learner_report, user_id, attempt_id))
