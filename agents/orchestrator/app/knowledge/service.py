"""Knowledge tests: an organization admin uploads documents (PDF, Word,
PowerPoint, text, images), chooses how many questions and of which kind
(multiple choice, written/spoken answers, or both), and the model writes the
questions and answers from the documents. The admin reviews and edits them,
then shares the test as an assessment link (app/proctoring). Learners take
it in an interview-style screen; multiple choice is marked here, other
answers are graded by the model, and the report is kept on the attempt.

Only the organization's admins (and DigiDARA's platform admin) can see or
change a test and its answers; learners only ever receive the questions.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from app import db
from app.knowledge import extract, generate
from app.models import (
    Assessment,
    KnowledgeAttempt,
    KnowledgeDocument,
    KnowledgeQuestion,
    KnowledgeTest,
    Organization,
    ProctorSession,
    User,
)
# Modules, not names (see app/proctoring/service.py on the import cycle).
from app.organizations import service as org_service
from app.proctoring import service as proctoring_service

logger = logging.getLogger("orchestrator.knowledge")

QUESTION_TYPES = ("mcq", "qa", "mixed")
MAX_QUESTIONS = 50
MAX_DOCUMENTS = 15
MAX_TESTS = 500
# A test still "generating" after this long lost its worker (a restart).
STUCK_AFTER = timedelta(minutes=15)


class KnowledgeError(Exception):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def _now() -> datetime:
    return datetime.utcnow()


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() + "Z" if value else None


def _clean(value: object, limit: int) -> str:
    return " ".join(str(value or "").split())[:limit]


def _admin(session, user_id: str, org_id: str) -> None:
    try:
        org_service._require_admin(session, user_id, org_id)
    except org_service.OrgError as exc:
        raise KnowledgeError(exc.status_code, exc.message) from exc


def _test(session, org_id: str, test_id: str) -> KnowledgeTest:
    test = session.get(KnowledgeTest, test_id)
    if test is None or test.organization_id != org_id:
        raise KnowledgeError(404, "No such knowledge test in this organization.")
    if test.status == "generating" and test.updated_at and _now() - test.updated_at > STUCK_AFTER:
        test.status, test.error = "failed", "Writing the questions was interrupted. Please generate again."
        session.commit()
    return test


def _locked(session, test: KnowledgeTest) -> bool:
    """Learners have started it: its questions can no longer change."""
    return session.query(KnowledgeAttempt).filter_by(test_id=test.id).first() is not None


def _question_admin(q: KnowledgeQuestion) -> dict:
    return {"id": q.id, "position": q.position, "qtype": q.qtype, "question": q.question, "options": q.options or [],
            "correct": q.correct, "answer": q.answer, "explanation": q.explanation}


def _test_dict(session, test: KnowledgeTest, full: bool = False) -> dict:
    documents = (session.query(KnowledgeDocument.id, KnowledgeDocument.filename, KnowledgeDocument.kind,
                               KnowledgeDocument.chars, KnowledgeDocument.created_at)
                 .filter_by(test_id=test.id).order_by(KnowledgeDocument.created_at).all())
    questions = session.query(KnowledgeQuestion).filter_by(test_id=test.id).order_by(KnowledgeQuestion.position).all()
    data = {
        "id": test.id, "title": test.title, "question_type": test.question_type, "num_questions": test.num_questions,
        "seconds_per_question": test.seconds_per_question, "instructions": test.instructions,
        "status": test.status, "error": test.error, "question_count": len(questions),
        "document_count": len(documents), "locked": _locked(session, test),
        "created_at": _iso(test.created_at), "updated_at": _iso(test.updated_at),
    }
    if full:
        data["documents"] = [{"id": d_id, "filename": name, "kind": kind, "chars": chars, "created_at": _iso(at)}
                             for d_id, name, kind, chars, at in documents]
        data["questions"] = [_question_admin(q) for q in questions]
    return data


def _settings(question_type: object, num_questions: object, seconds: object) -> tuple[str, int, int]:
    if question_type not in QUESTION_TYPES:
        raise KnowledgeError(400, "Choose multiple choice, written answers, or both.")
    try:
        count = int(num_questions)
        per_question = int(seconds)
    except (TypeError, ValueError) as exc:
        raise KnowledgeError(400, "Enter the number of questions and the time per question.") from exc
    if not 1 <= count <= MAX_QUESTIONS:
        raise KnowledgeError(400, f"Choose between 1 and {MAX_QUESTIONS} questions.")
    return str(question_type), count, max(20, min(per_question, 600))


# --- the organization's admins -------------------------------------------------

def list_tests(user_id: str, org_id: str) -> list[dict]:
    session = db.get_session()
    try:
        _admin(session, user_id, org_id)
        tests = session.query(KnowledgeTest).filter_by(organization_id=org_id).order_by(KnowledgeTest.created_at.desc()).all()
        return [_test_dict(session, test) for test in tests]
    finally:
        session.close()


def create_test(user_id: str, org_id: str, data: dict) -> dict:
    title = _clean(data.get("title"), 200)
    if len(title) < 3:
        raise KnowledgeError(400, "Give the test a title.")
    question_type, count, seconds = _settings(data.get("question_type"), data.get("num_questions", 10),
                                              data.get("seconds_per_question", 90))
    session = db.get_session()
    try:
        _admin(session, user_id, org_id)
        if session.query(KnowledgeTest).filter_by(organization_id=org_id).count() >= MAX_TESTS:
            raise KnowledgeError(409, f"An organization can have at most {MAX_TESTS} knowledge tests.")
        test = KnowledgeTest(organization_id=org_id, created_by=user_id, title=title, question_type=question_type,
                             num_questions=count, seconds_per_question=seconds,
                             instructions=str(data.get("instructions") or "").strip()[:2000])
        session.add(test)
        session.commit()
        return _test_dict(session, test, full=True)
    finally:
        session.close()


def get_test(user_id: str, org_id: str, test_id: str) -> dict:
    session = db.get_session()
    try:
        _admin(session, user_id, org_id)
        return _test_dict(session, _test(session, org_id, test_id), full=True)
    finally:
        session.close()


def update_test(user_id: str, org_id: str, test_id: str, data: dict) -> dict:
    session = db.get_session()
    try:
        _admin(session, user_id, org_id)
        test = _test(session, org_id, test_id)
        if "title" in data:
            title = _clean(data.get("title"), 200)
            if len(title) < 3:
                raise KnowledgeError(400, "Give the test a title.")
            test.title = title
        if "seconds_per_question" in data:
            _, _, test.seconds_per_question = _settings(test.question_type, test.num_questions, data["seconds_per_question"])
        if "question_type" in data or "num_questions" in data or "instructions" in data:
            if _locked(session, test):
                raise KnowledgeError(409, "Learners have already taken this test, so its questions cannot change. Create a new test instead.")
            test.question_type, test.num_questions, _ = _settings(
                data.get("question_type", test.question_type), data.get("num_questions", test.num_questions), test.seconds_per_question)
            if "instructions" in data:
                test.instructions = str(data.get("instructions") or "").strip()[:2000]
        session.commit()
        return _test_dict(session, test, full=True)
    finally:
        session.close()


def delete_test(user_id: str, org_id: str, test_id: str) -> None:
    session = db.get_session()
    try:
        _admin(session, user_id, org_id)
        test = _test(session, org_id, test_id)
        for assessment in session.query(Assessment).filter_by(organization_id=org_id, kind="knowledge_test").all():
            if (assessment.config or {}).get("test_id") == test.id:
                assessment.active = False
        session.delete(test)
        session.commit()
    finally:
        session.close()


def add_documents(user_id: str, org_id: str, test_id: str, files: list[tuple[str, bytes]]) -> dict:
    """Reads each file; returns the test and, per file, what happened."""
    session = db.get_session()
    try:
        _admin(session, user_id, org_id)
        test = _test(session, org_id, test_id)
        if _locked(session, test):
            raise KnowledgeError(409, "Learners have already taken this test, so its material cannot change. Create a new test instead.")
        existing = session.query(KnowledgeDocument).filter_by(test_id=test.id).count()
    finally:
        session.close()
    results = []
    readable: list[tuple[str, str, str]] = []
    for filename, data in files:
        name = _clean(filename, 255) or "document"
        if existing + len(readable) >= MAX_DOCUMENTS:
            results.append({"filename": name, "ok": False, "message": f"A test can have at most {MAX_DOCUMENTS} documents."})
            continue
        try:
            kind, text = extract.extract(name, data)
        except extract.ExtractError as exc:
            results.append({"filename": name, "ok": False, "message": str(exc)})
            continue
        readable.append((name, kind, text))
        results.append({"filename": name, "ok": True, "chars": len(text)})
    session = db.get_session()
    try:
        test = _test(session, org_id, test_id)
        for name, kind, text in readable:
            session.add(KnowledgeDocument(test_id=test.id, filename=name, kind=kind, chars=len(text), text=text))
        session.commit()
        return {"test": _test_dict(session, test, full=True), "results": results}
    finally:
        session.close()


def delete_document(user_id: str, org_id: str, test_id: str, document_id: str) -> dict:
    session = db.get_session()
    try:
        _admin(session, user_id, org_id)
        test = _test(session, org_id, test_id)
        if _locked(session, test):
            raise KnowledgeError(409, "Learners have already taken this test, so its material cannot change.")
        document = session.get(KnowledgeDocument, document_id)
        if document is None or document.test_id != test.id:
            raise KnowledgeError(404, "No such document in this test.")
        session.delete(document)
        session.commit()
        return _test_dict(session, test, full=True)
    finally:
        session.close()


def start_generation(user_id: str, org_id: str, test_id: str) -> dict:
    """Marks the test as generating; the route runs run_generation afterwards."""
    session = db.get_session()
    try:
        _admin(session, user_id, org_id)
        test = _test(session, org_id, test_id)
        if _locked(session, test):
            raise KnowledgeError(409, "Learners have already taken this test, so its questions cannot change. Create a new test instead.")
        if test.status == "generating":
            raise KnowledgeError(409, "The questions are already being written.")
        if session.query(KnowledgeDocument).filter_by(test_id=test.id).count() == 0:
            raise KnowledgeError(400, "Upload at least one document first.")
        test.status, test.error = "generating", ""
        test.updated_at = _now()
        session.commit()
        return _test_dict(session, test, full=True)
    finally:
        session.close()


def run_generation(test_id: str) -> None:
    """Writes the questions (runs after the request returns)."""
    session = db.get_session()
    try:
        test = session.get(KnowledgeTest, test_id)
        if test is None:
            return
        documents = [(d.filename, d.text) for d in session.query(KnowledgeDocument).filter_by(test_id=test_id)
                     .order_by(KnowledgeDocument.created_at).all()]
        question_type, count, instructions = test.question_type, test.num_questions, test.instructions
    finally:
        session.close()
    try:
        written = generate.write_questions(generate.build_context(documents), question_type, count, instructions)
    except Exception:
        logger.exception("knowledge generation failed for test %s", test_id)
        written = []
    session = db.get_session()
    try:
        test = session.get(KnowledgeTest, test_id)
        if test is None:
            return
        if not written:
            test.status, test.error = "failed", "No questions could be written from these documents. Check they have enough readable content and try again."
        else:
            session.query(KnowledgeQuestion).filter_by(test_id=test_id).delete(synchronize_session=False)
            for position, question in enumerate(written, start=1):
                session.add(KnowledgeQuestion(test_id=test_id, position=position, **question))
            test.status = "ready"
            test.error = "" if len(written) >= count else f"Only {len(written)} of {count} questions could be written from this material."
        test.updated_at = _now()
        session.commit()
    finally:
        session.close()


def update_question(user_id: str, org_id: str, test_id: str, question_id: str, data: dict) -> dict:
    session = db.get_session()
    try:
        _admin(session, user_id, org_id)
        test = _test(session, org_id, test_id)
        if _locked(session, test):
            raise KnowledgeError(409, "Learners have already taken this test, so its questions cannot change.")
        q = session.get(KnowledgeQuestion, question_id)
        if q is None or q.test_id != test.id:
            raise KnowledgeError(404, "No such question in this test.")
        text = _clean(data.get("question", q.question), 1000)
        if len(text) < 5:
            raise KnowledgeError(400, "Enter the question.")
        q.question = text
        q.explanation = _clean(data.get("explanation", q.explanation), 1000)
        if q.qtype == "mcq":
            options = [_clean(option, 300) for option in data.get("options", q.options) or []]
            try:
                correct = int(data.get("correct", q.correct))
            except (TypeError, ValueError) as exc:
                raise KnowledgeError(400, "Choose the right answer.") from exc
            if len(options) != 4 or not all(options) or not 0 <= correct < 4:
                raise KnowledgeError(400, "A multiple choice question needs four options and one right answer.")
            q.options, q.correct, q.answer = options, correct, options[correct]
        else:
            answer = _clean(data.get("answer", q.answer), 2000)
            if len(answer) < 2:
                raise KnowledgeError(400, "Enter the model answer.")
            q.answer = answer
        session.commit()
        return _question_admin(q)
    finally:
        session.close()


def delete_question(user_id: str, org_id: str, test_id: str, question_id: str) -> dict:
    session = db.get_session()
    try:
        _admin(session, user_id, org_id)
        test = _test(session, org_id, test_id)
        if _locked(session, test):
            raise KnowledgeError(409, "Learners have already taken this test, so its questions cannot change.")
        q = session.get(KnowledgeQuestion, question_id)
        if q is None or q.test_id != test.id:
            raise KnowledgeError(404, "No such question in this test.")
        session.delete(q)
        session.flush()
        for position, rest in enumerate(session.query(KnowledgeQuestion).filter_by(test_id=test.id)
                                        .order_by(KnowledgeQuestion.position).all(), start=1):
            rest.position = position
        session.commit()
        return _test_dict(session, test, full=True)
    finally:
        session.close()


def assessment_config(org_id: str, test_id: str) -> dict:
    """What an assessment link stores about the test it runs."""
    session = db.get_session()
    try:
        test = session.get(KnowledgeTest, str(test_id or ""))
        if test is None or test.organization_id != org_id:
            raise KnowledgeError(400, "Choose one of this organization's knowledge tests.")
        count = session.query(KnowledgeQuestion).filter_by(test_id=test.id).count()
        if test.status != "ready" or count == 0:
            raise KnowledgeError(400, "This knowledge test has no questions yet. Generate them first.")
        return {"test_id": test.id, "test_title": test.title, "question_type": test.question_type,
                "num_questions": count, "seconds_per_question": test.seconds_per_question}
    finally:
        session.close()


# --- the learner -------------------------------------------------------------------

def _question_learner(q: KnowledgeQuestion) -> dict:
    return {"id": q.id, "position": q.position, "qtype": q.qtype, "question": q.question, "options": q.options or []}


def _attempt_view(session, attempt: KnowledgeAttempt, test: KnowledgeTest) -> dict:
    questions = session.query(KnowledgeQuestion).filter_by(test_id=test.id).order_by(KnowledgeQuestion.position).all()
    return {
        "id": attempt.id, "status": attempt.status, "title": test.title, "question_type": test.question_type,
        "seconds_per_question": test.seconds_per_question,
        "questions": [_question_learner(q) for q in questions],
        "answered": sorted((attempt.answers or {}).keys()),
        "report": attempt.report if attempt.status == "completed" else None,
    }


def start_attempt(user_id: str, proctor_session_id: str) -> dict:
    """The learner's attempt for an assessment link's (already agreed) session."""
    session = db.get_session()
    try:
        ps = session.get(ProctorSession, proctor_session_id)
        if ps is None or ps.user_id != user_id or not ps.assessment_id:
            raise KnowledgeError(404, "Open the assessment link to start this test.")
        assessment = session.get(Assessment, ps.assessment_id)
        if assessment is None or assessment.kind != "knowledge_test":
            raise KnowledgeError(404, "This assessment is not a knowledge test.")
        attempt = session.query(KnowledgeAttempt).filter_by(proctor_session_id=ps.id).first()
        test = session.get(KnowledgeTest, (assessment.config or {}).get("test_id", ""))
        if test is None:
            raise KnowledgeError(410, "This test was removed by the organization.")
        if attempt is None:
            if ps.status != "active":
                raise KnowledgeError(409, "This assessment has already ended.")
            attempt = KnowledgeAttempt(test_id=test.id, user_id=user_id, proctor_session_id=ps.id, answers={})
            session.add(attempt)
            session.flush()
            ps.ref = attempt.id
            session.commit()
        return _attempt_view(session, attempt, test)
    finally:
        session.close()


def _own_attempt(session, user_id: str, attempt_id: str) -> tuple[KnowledgeAttempt, KnowledgeTest]:
    attempt = session.get(KnowledgeAttempt, attempt_id)
    if attempt is None or attempt.user_id != user_id:
        raise KnowledgeError(404, "No such test attempt.")
    test = session.get(KnowledgeTest, attempt.test_id)
    if test is None:
        raise KnowledgeError(410, "This test was removed by the organization.")
    return attempt, test


def submit_answer(user_id: str, attempt_id: str, question_id: str, answer: str, time_taken: float, timed_out: bool) -> dict:
    session = db.get_session()
    try:
        attempt, test = _own_attempt(session, user_id, attempt_id)
        if attempt.status != "active":
            raise KnowledgeError(409, "This test has already been submitted.")
        q = session.get(KnowledgeQuestion, question_id)
        if q is None or q.test_id != test.id:
            raise KnowledgeError(404, "No such question in this test.")
        answers = dict(attempt.answers or {})
        if question_id in answers:
            return {"answered": sorted(answers.keys())}
        value = str(answer or "").strip()
        if q.qtype == "mcq":
            value = value if value in ("0", "1", "2", "3") else ""
        answers[question_id] = {"answer": value[:5000], "time_taken": max(0, min(int(time_taken or 0), 3600)),
                                "timed_out": bool(timed_out)}
        attempt.answers = answers
        session.commit()
        return {"answered": sorted(answers.keys())}
    finally:
        session.close()


def _build_report(session, attempt: KnowledgeAttempt, test: KnowledgeTest) -> dict:
    questions = session.query(KnowledgeQuestion).filter_by(test_id=test.id).order_by(KnowledgeQuestion.position).all()
    answers = attempt.answers or {}
    graded = generate.grade_answers([
        {"id": q.id, "question": q.question, "model_answer": q.answer, "answer": answers.get(q.id, {}).get("answer", "")}
        for q in questions if q.qtype == "qa"
    ])
    rows, total = [], 0.0
    for number, q in enumerate(questions, start=1):
        given = answers.get(q.id, {})
        raw = given.get("answer", "")
        if q.qtype == "mcq":
            chosen = int(raw) if raw in ("0", "1", "2", "3") else None
            right = chosen is not None and chosen == q.correct
            points = 1.0 if right else 0.0
            verdict = "correct" if right else "wrong"
            your = (q.options or [])[chosen] if chosen is not None and chosen < len(q.options or []) else ""
            feedback = "" if right else (q.explanation or "")
        else:
            grade = graded.get(q.id, {"score": None, "verdict": "ungraded", "feedback": ""})
            points = (grade["score"] or 0) / 10
            verdict, your, feedback = grade["verdict"], raw, grade["feedback"]
        total += points
        rows.append({
            "number": number, "qtype": q.qtype, "question": q.question, "options": q.options or [],
            "your_answer": your, "correct_answer": q.answer, "verdict": verdict, "points": round(points, 2),
            "feedback": feedback, "explanation": q.explanation,
            "time_taken": given.get("time_taken"), "timed_out": bool(given.get("timed_out")), "answered": bool(raw),
        })
    maximum = float(len(questions)) or 1.0
    percent = round(100 * total / maximum, 1)
    return {"score": round(total, 1), "max": int(maximum), "percent": percent, "rows": rows,
            **generate.summarize(test.title, rows, percent)}


def finish_attempt(user_id: str, attempt_id: str) -> dict:
    """Marks and grades the attempt and keeps its report (once)."""
    session = db.get_session()
    try:
        attempt, test = _own_attempt(session, user_id, attempt_id)
        if attempt.status == "completed":
            return _attempt_view(session, attempt, test)
    finally:
        session.close()
    session = db.get_session()
    try:
        attempt, test = _own_attempt(session, user_id, attempt_id)
        report = _build_report(session, attempt, test)
        user = session.get(User, user_id)
        org = session.get(Organization, test.organization_id)
        ps = session.get(ProctorSession, attempt.proctor_session_id) if attempt.proctor_session_id else None
        report.update({
            "title": test.title, "organization": org.name if org else "", "learner": user.name if user else "",
            "email": user.email if user else "", "finished_at": _iso(_now()),
            "integrity": ps.integrity if ps else None, "proctor_status": ps.status if ps else None,
        })
        attempt.report, attempt.score, attempt.max_score = report, report["score"], report["max"]
        attempt.status, attempt.finished_at = "completed", _now()
        if ps is not None:
            ps.result = {"score": report["score"], "max": report["max"], "percent": report["percent"]}
            if ps.status == "active":
                ps.status, ps.ended_at = "completed", _now()
        session.commit()
        return _attempt_view(session, attempt, test)
    finally:
        session.close()


def learner_report(user_id: str, attempt_id: str) -> dict:
    session = db.get_session()
    try:
        attempt, _ = _own_attempt(session, user_id, attempt_id)
        if attempt.status != "completed" or not attempt.report:
            raise KnowledgeError(409, "The report is ready once the test is submitted.")
        return attempt.report
    finally:
        session.close()


def admin_report(admin_id: str, org_id: str, proctor_session_id: str) -> dict:
    """An attempt's report for the organization's admins (logged like any proctoring report)."""
    proctoring_service.session_detail(admin_id, org_id, proctor_session_id)  # access check + access log
    session = db.get_session()
    try:
        attempt = session.query(KnowledgeAttempt).filter_by(proctor_session_id=proctor_session_id).first()
        if attempt is None:
            raise KnowledgeError(404, "This learner has not started the test yet.")
        if attempt.status != "completed" or not attempt.report:
            raise KnowledgeError(409, "This learner has not finished the test yet.")
        return attempt.report
    finally:
        session.close()
