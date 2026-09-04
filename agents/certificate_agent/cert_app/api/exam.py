from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional

from cert_app.schemas.exam import StartExamRequest, AnswerSubmit
from cert_app.services.exam_service import (
    start_exam, submit_exam, get_user_exams,
    get_exam_detail, get_leaderboard
)
from cert_app.services.auth_service import verify_token
from cert_app.db import chat_repository

router = APIRouter()
security = HTTPBearer()


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    payload = verify_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return payload


@router.post("/start")
def start(request: StartExamRequest, user=Depends(get_current_user)):
    try:
        return start_exam(int(user["sub"]), user["name"], request.topic)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/submit")
def submit(request: AnswerSubmit, user=Depends(get_current_user)):
    try:
        answers = [a.dict() for a in request.answers]
        return submit_exam(int(user["sub"]), user["name"], request.exam_id, answers)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history")
def history(user=Depends(get_current_user)):
    exams = get_user_exams(int(user["sub"]))
    for e in exams:
        for k, v in e.items():
            if hasattr(v, 'isoformat'):
                e[k] = str(v)
    return exams


@router.get("/leaderboard")
def leaderboard(topic: Optional[str] = None):
    return get_leaderboard(topic)


@router.get("/chat-session/{session_id}/questions")
def get_chat_session_questions(session_id: str, user=Depends(get_current_user)):
    """
    Retrieve or initialize the official exam in the database from a chat session.
    Persists questions into the questions table so they get correct database auto-increment IDs.
    """
    user_id = int(user["sub"])
    session = chat_repository.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")
    if session["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    # 1. If an exam is already created and linked for this session, return it
    exam_id = session.get("exam_id")
    if exam_id:
        try:
            exam_detail = get_exam_detail(user_id, exam_id)
            # Normalize database questions for exam.html
            questions = []
            for q in exam_detail.get("questions", []):
                # options is stored as JSON in DB and parsed in get_exam_detail
                opts = q.get("options", [])
                if isinstance(opts, str):
                    try:
                        import json
                        opts = json.loads(opts)
                    except Exception:
                        opts = []
                questions.append({
                    "id": q["id"],
                    "question_text": q["question_text"],
                    "options": opts,
                    "correct_answer": q.get("correct_answer", ""),
                    "difficulty": q.get("difficulty", "beginner")
                })
            return {
                "exam_id": exam_id,
                "topic": session.get("topic", ""),
                "total_questions": len(questions),
                "questions": questions
            }
        except Exception as e:
            # If load fails, we will fall back to recreating
            pass

    # 2. Load the pre-generated questions from the chat session metadata
    raw_questions = chat_repository.get_session_questions(session_id)
    if not raw_questions:
        raise HTTPException(status_code=404, detail="No pre-generated questions found. Please start a new session.")

    # 3. Create the exam in the database and store questions
    from cert_app.db.database import get_connection
    import json
    from cert_app.services.exam_service import increment_attempt

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        # Insert exams row
        cursor.execute(
            "INSERT INTO exams (user_id, topic, total_questions, status) VALUES (%s,%s,%s,'in_progress')",
            (user_id, session.get("topic", ""), len(raw_questions))
        )
        exam_id = cursor.lastrowid

        # Insert questions rows
        question_records = []
        for i, q in enumerate(raw_questions):
            options_json = json.dumps(q.get("options", []))
            cursor.execute(
                """INSERT INTO questions (exam_id, question_text, expected_answer, options, correct_answer, difficulty, order_num) 
                   VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                (
                    exam_id, 
                    q.get("question", q.get("question_text", "")), 
                    q.get("expected_answer", ""), 
                    options_json, 
                    q.get("correct_answer", ""), 
                    q.get("difficulty", "beginner"), 
                    i + 1
                )
            )
            question_records.append({
                "id": cursor.lastrowid,
                "question_text": q.get("question", q.get("question_text", "")),
                "options": q.get("options", []),
                "difficulty": q.get("difficulty", "beginner"),
                "order_num": i + 1
            })

        # Update conversation session to link this exam_id and set status to 'in_exam'
        cursor.execute(
            "UPDATE conversation_sessions SET exam_id = %s, status = 'in_exam' WHERE id = %s",
            (exam_id, session_id)
        )
        conn.commit()

        # Increment attempts tracking
        increment_attempt(user_id, session.get("topic", ""))

        return {
            "exam_id": exam_id,
            "topic": session.get("topic", ""),
            "total_questions": len(raw_questions),
            "questions": question_records
        }
    finally:
        cursor.close()
        conn.close()


@router.get("/{exam_id}")
def detail(exam_id: int, user=Depends(get_current_user)):
    try:
        exam = get_exam_detail(int(user["sub"]), exam_id)
        for k, v in exam.items():
            if hasattr(v, 'isoformat'):
                exam[k] = str(v)
        return exam
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

