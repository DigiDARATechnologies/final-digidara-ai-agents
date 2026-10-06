"""Writing practice returns every correction the evaluator found (up to six)."""
import json

from app.services import groq_writing


def test_all_six_corrections_reach_the_learner(monkeypatch):
    mistakes = [{"incorrect": f"wrong {i}", "correct": f"right {i}", "explanation": f"reason {i}"} for i in range(6)]
    reply = json.dumps({"corrected_answer": "Fixed.", "mistakes": mistakes,
                        "scores": {"grammar": 6, "vocabulary": 6, "clarity": 6, "spelling": 6, "relevance": 6, "overall": 6}})
    monkeypatch.setattr(groq_writing, "_chat", lambda *a, **k: reply)
    feedback = groq_writing.evaluate_writing_answer("daily", "medium", "Teamwork", "Why is teamwork important?", "wrong 0 wrong 1")
    assert [m["incorrect"] for m in feedback["mistakes"]] == [f"wrong {i}" for i in range(6)]
    assert all(m["correct"] and m["explanation"] for m in feedback["mistakes"])
    assert feedback["corrected_answer"] == "Fixed."
