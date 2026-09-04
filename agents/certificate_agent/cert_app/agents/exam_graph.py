import logging
from typing import TypedDict, List, Optional

from langgraph.graph import StateGraph, END

from cert_app.agents.question_agent import generate_questions
from cert_app.agents.evaluation_agent import evaluate_answer
from cert_app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


# ─── State Schema ─────────────────────────────────────────────────────────────

class ExamState(TypedDict):
    user_id: int
    username: str
    topic: str
    exam_id: int
    questions: List[dict]
    user_answers: List[dict]
    evaluations: List[dict]
    correct_count: int
    total_count: int
    score_percentage: float
    passed: bool
    certificate_path: Optional[str]
    error: Optional[str]


# ─── Graph Nodes ───────────────────────────────────────────────────────────────

def node_generate_questions(state: ExamState) -> ExamState:
    logger.info(f"[Graph] Generating questions for: {state['topic']}")
    try:
        questions = generate_questions(state["topic"])
        return {**state, "questions": questions, "total_count": len(questions), "error": None}
    except Exception as e:
        logger.error(f"[Graph] Question generation error: {e}")
        return {**state, "questions": [], "total_count": 0, "error": str(e)}


def node_evaluate_answers(state: ExamState) -> ExamState:
    logger.info(f"[Graph] Evaluating {len(state['user_answers'])} answers")
    evaluations = []
    correct_count = 0
    questions = state.get("questions", [])

    for i, ans in enumerate(state["user_answers"]):
        q = questions[i] if i < len(questions) else {}
        user_ans = str(ans.get("answer", "")).strip()
        opts = q.get("options", [])
        
        if opts and len(opts) > 0:
            is_correct = (user_ans == str(q.get("correct_answer", "")).strip())
            score = 1 if is_correct else 0
            feedback = f"Correct! {q.get('expected_answer', '')}" if is_correct else f"Incorrect. Correct: {q.get('correct_answer', '')}"
        else:
            res = evaluate_answer(
                q.get("question", ""),
                q.get("expected_answer", ""),
                user_ans
            )
            score = res["score"]
            feedback = res["feedback"]

        evaluations.append({
            "question_id": ans.get("question_id"),
            "score": score,
            "feedback": feedback
        })
        correct_count += score

    return {**state, "evaluations": evaluations, "correct_count": correct_count}


def node_calculate_score(state: ExamState) -> ExamState:
    total = max(state.get("total_count", 1), 1)
    score = round((state["correct_count"] / total) * 100, 2)
    passed = score >= settings.PASS_SCORE
    logger.info(f"[Graph] Score: {score}% — {'PASSED' if passed else 'FAILED'}")
    return {**state, "score_percentage": score, "passed": passed}


def _should_generate_cert(state: ExamState) -> str:
    return "generate_certificate" if state.get("passed") else END


def node_generate_certificate(state: ExamState) -> ExamState:
    from cert_app.services.certificate_generator import generate_certificate
    from cert_app.services.exam_service import is_topic_course
    import uuid
    cert_number = str(uuid.uuid4())[:8].upper()
    is_course = is_topic_course(state["topic"])
    path = generate_certificate(state["username"], state["topic"], state["score_percentage"], cert_number, is_course_final=is_course)
    logger.info(f"[Graph] Certificate generated: {path}")
    return {**state, "certificate_path": path}


# ─── Graph Builders ───────────────────────────────────────────────────────────

def build_question_graph():
    wf = StateGraph(ExamState)
    wf.add_node("generate_questions", node_generate_questions)
    wf.set_entry_point("generate_questions")
    wf.add_edge("generate_questions", END)
    return wf.compile()


def build_evaluation_graph():
    wf = StateGraph(ExamState)
    wf.add_node("evaluate_answers", node_evaluate_answers)
    wf.add_node("calculate_score", node_calculate_score)
    wf.add_node("generate_certificate", node_generate_certificate)
    wf.set_entry_point("evaluate_answers")
    wf.add_edge("evaluate_answers", "calculate_score")
    wf.add_conditional_edges("calculate_score", _should_generate_cert)
    return wf.compile()


# Compiled graphs (singletons)
question_graph = build_question_graph()
evaluation_graph = build_evaluation_graph()
