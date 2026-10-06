"""Ending a "Chat with AI" writing conversation saves a scored session with a
PDF report, and every writing PDF lists the corrections."""
import base64

import pytest
from reportlab import rl_config

from app.routes import writing as routes

HISTORY = [
    {"role": "assistant", "text": "What do you like about teamwork?"},
    {"role": "user", "text": "I likes teamwork because we shares ideas."},
    {"role": "assistant", "text": "Nice! Tell me about a team project."},
    {"role": "user", "text": "We builded a website for our college."},
]


@pytest.fixture
def evaluator(monkeypatch):
    seen = []

    def evaluate(mode, difficulty, topic, question, answer):
        seen.append({"mode": mode, "question": question, "answer": answer})
        wrong = "I likes" if "likes" in answer else "builded"
        right = "I like" if "likes" in answer else "built"
        return {
            "corrected_answer": answer.replace(wrong, right),
            "mistakes": [{"incorrect": wrong, "correct": right, "explanation": f"Use '{right}' here."}],
            "scores": {"grammar": 6, "vocabulary": 7, "clarity": 7, "overall": 6.5},
            "short_feedback": "Good effort.",
        }

    monkeypatch.setattr(routes.groq_service, "evaluate_writing_answer", evaluate)
    monkeypatch.setattr(routes.groq_service, "summarize_writing_session", lambda *a, **k: {
        "summary_feedback": "You shared clear ideas about teamwork.", "strengths": ["Clear ideas"],
        "areas_to_improve": ["Verb forms"], "common_mistakes": [], "recommendation": "Practise past tense.",
        "next_practice_suggestion": "Write about a trip."})
    return seen


def finish(client, headers, history=HISTORY):
    return client.post("/api/writing/chat/finish", json={"topic": "Teamwork", "difficulty": "medium", "history": history}, headers=headers)


def test_finishing_a_chat_evaluates_each_message_and_saves_a_session(client, auth_headers, evaluator):
    response = finish(client, auth_headers)
    assert response.status_code == 200, response.get_json()
    body = response.get_json()
    assert body["session_id"] and body["total_turns"] == 2
    assert body["summary_feedback"] == "You shared clear ideas about teamwork."
    # Each learner message is judged against the question the AI asked just before it.
    assert [(s["question"], s["answer"]) for s in evaluator] == [
        ("What do you like about teamwork?", "I likes teamwork because we shares ideas."),
        ("Nice! Tell me about a team project.", "We builded a website for our college."),
    ]


def test_the_chat_report_pdf_lists_each_correction(client, auth_headers, evaluator, monkeypatch):
    monkeypatch.setattr(rl_config, "pageCompression", 0)
    session_id = finish(client, auth_headers).get_json()["session_id"]
    response = client.get(f"/api/writing/report/{session_id}/pdf?format=json", headers=auth_headers)
    assert response.status_code == 200
    pdf = base64.b64decode(response.get_json()["pdf_base64"])
    assert pdf.startswith(b"%PDF")
    # (PDF text escapes parentheses.)
    for text in (rb"Corrections \(1\):", b"builded", b"built", b"Use 'built' here.", b"I likes", b"Corrected Answer:"):
        assert text in pdf, text


def test_a_chat_with_no_learner_message_has_nothing_to_report(client, auth_headers, evaluator):
    response = finish(client, auth_headers, history=[{"role": "assistant", "text": "Hi! What do you think?"}])
    assert response.status_code == 400 and response.get_json()["error_code"] == "EMPTY_CHAT"
    assert evaluator == []


def test_only_the_learners_own_report_can_be_downloaded(client, auth_headers, evaluator, make_user_headers):
    session_id = finish(client, auth_headers).get_json()["session_id"]
    other = make_user_headers()
    assert client.get(f"/api/writing/report/{session_id}/pdf?format=json", headers=other).status_code == 404


def test_a_long_chat_reports_its_latest_ten_messages(client, auth_headers, evaluator):
    history = []
    for n in range(14):
        history += [{"role": "assistant", "text": f"Question {n}?"}, {"role": "user", "text": f"I likes answer {n}."}]
    assert finish(client, auth_headers, history=history).get_json()["total_turns"] == 10
    assert evaluator[0]["answer"] == "I likes answer 4."
