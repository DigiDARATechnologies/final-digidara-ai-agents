"""A session is scored only from answers that were actually evaluated: no
answers, or answers that could not be scored, never show a made-up 75."""
import pytest

from app.routes import speaking
from app.services import groq_speaking


def _start(client, auth_headers, monkeypatch):
    monkeypatch.setattr(speaking.groq_service, "generate_speaking_question", lambda *a, **k: "What did you learn this week?")
    response = client.post(
        "/api/speaking/start",
        json={"mode": "topic", "difficulty": "medium", "topic_title": "Learning", "topic_description": "Talk about learning."},
        headers=auth_headers,
    )
    assert response.status_code == 201
    return response.get_json()["session_id"]


def _feedback(scores):
    return {
        "appreciation": "Thanks.", "status": "Needs Review", "original_answer": "x", "corrected_answer": "x",
        "explanation": "", "mistakes": [], "vocabulary_suggestions": [], "better_natural_answer": "x",
        "short_feedback": "", "scores": scores,
    }


def test_ending_a_session_without_speaking_shows_no_score(client, auth_headers, monkeypatch):
    session_id = _start(client, auth_headers, monkeypatch)
    summary = client.post("/api/speaking/end", json={"session_id": session_id}, headers=auth_headers).get_json()["summary"]
    assert summary["answered_turns"] == 0
    for key in ("overall_score", "confidence_score", "fluency_score", "grammar_score", "clarity_score"):
        assert summary[key] is None, key
    assert summary["executive_scorecard"]["scores_breakdown"] is None
    assert summary["executive_scorecard"]["you_did_well"] is None


def test_an_answer_that_could_not_be_scored_is_not_a_flat_75(client, auth_headers, monkeypatch):
    session_id = _start(client, auth_headers, monkeypatch)
    monkeypatch.setattr(speaking.groq_service, "evaluate_speaking_answer", lambda *a, **k: _feedback(
        {"confidence": None, "fluency": None, "grammar": None, "knowledge": None, "overall": None}))
    monkeypatch.setattr(speaking.groq_service, "summarize_speaking_session", lambda *a, **k: {
        "summary_feedback": "Unclear audio.", "scores_breakdown": {"vocabulary": 60}})
    client.post("/api/speaking/respond", json={"session_id": session_id, "answer": "mm hmm"}, headers=auth_headers)
    summary = client.post("/api/speaking/end", json={"session_id": session_id}, headers=auth_headers).get_json()["summary"]
    assert summary["answered_turns"] == 1
    assert summary["overall_score"] is None
    assert summary["grammar_score"] is None
    # Nothing was scored, so there is no breakdown at all (not even the model's vocabulary guess).
    assert summary["executive_scorecard"]["scores_breakdown"] is None


def test_the_scorecard_uses_the_real_scores_of_the_answers(client, auth_headers, monkeypatch):
    session_id = _start(client, auth_headers, monkeypatch)
    monkeypatch.setattr(speaking.groq_service, "evaluate_speaking_answer", lambda *a, **k: _feedback(
        {"confidence": 40, "fluency": 30, "grammar": 50, "knowledge": 20, "overall": 35}))
    monkeypatch.setattr(speaking.groq_service, "summarize_speaking_session", lambda *a, **k: {
        "summary_feedback": "Short answers.",
        # The model's own overall is ignored; only vocabulary and sentence structure are its to judge.
        "scores_breakdown": {"overall": 75, "vocabulary": 45, "sentence_structure": "n/a"}})
    client.post("/api/speaking/respond", json={"session_id": session_id, "answer": "I learned some Python this week."}, headers=auth_headers)
    breakdown = client.post("/api/speaking/end", json={"session_id": session_id}, headers=auth_headers).get_json()["summary"]["executive_scorecard"]["scores_breakdown"]
    assert breakdown == {"overall": 35, "grammar": 50, "fluency": 30, "confidence": 40, "vocabulary": 45}


@pytest.mark.parametrize("text", ["", "Thank you.", "you", " Thanks for watching! ", "[BLANK_AUDIO]", "(music)", "...", "Um."])
def test_silence_transcripts_are_recognised(text):
    assert groq_speaking.is_silence_transcript(text)


@pytest.mark.parametrize("text", ["Thank you for asking, I learned Flask.", "Bye", "Okay", "I am fine"])
def test_real_short_answers_are_kept(text):
    assert not groq_speaking.is_silence_transcript(text)


def test_the_summary_never_invents_a_breakdown():
    assert groq_speaking._judged_scores({}, ("vocabulary", "sentence_structure")) == {}
    assert groq_speaking._judged_scores({"vocabulary": "62", "sentence_structure": 140}, ("vocabulary", "sentence_structure")) == {"vocabulary": 62}


def test_the_pdf_report_of_a_silent_session_is_built_without_scores(client, auth_headers, monkeypatch):
    session_id = _start(client, auth_headers, monkeypatch)
    client.post("/api/speaking/end", json={"session_id": session_id}, headers=auth_headers)
    response = client.get(f"/api/speaking/report/{session_id}/pdf", headers=auth_headers)
    assert response.status_code == 200
    assert response.data.startswith(b"%PDF")
