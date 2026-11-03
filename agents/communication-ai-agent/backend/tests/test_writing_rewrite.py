"""A learner can rewrite the same paragraph and be scored again, as often as they like."""
from flask_jwt_extended import decode_token

from app.extensions import db
from app.models import WritingSession, WritingTurn
from app.services import groq_service


def _feedback(*_args, **_kwargs):
    return {
        "corrected_answer": "I go to school.", "mistakes": [],
        "scores": {"grammar": 6, "vocabulary": 7, "clarity": 7, "overall": 6.5},
        "short_feedback": "Good effort.",
    }


def _session(auth_headers):
    user_id = int(decode_token(auth_headers["Authorization"].split()[1])["sub"])
    session = WritingSession(user_id=user_id, mode="topic", topic_title="School", difficulty="easy", total_turns=1)
    db.session.add(session)
    db.session.flush()
    db.session.add(WritingTurn(session_id=session.id, turn_number=1, ai_prompt="Write about your school."))
    db.session.commit()
    return session.id


def _submit(client, auth_headers, session_id, answer, **extra):
    return client.post("/api/writing/respond", headers=auth_headers, json={
        "session_id": session_id, "answer": answer, "finalize_after_submission": True, **extra,
    })


def test_each_rewrite_is_a_new_scored_attempt_at_the_same_prompt(client, auth_headers, monkeypatch):
    monkeypatch.setattr(groq_service, "evaluate_writing_answer", _feedback)
    session_id = _session(auth_headers)
    assert _submit(client, auth_headers, session_id, "I goes to school.").status_code == 200
    for attempt in ("I go to school.", "I go to school every day."):
        response = _submit(client, auth_headers, session_id, attempt, rewrite=True)
        assert response.status_code == 200, response.get_json()
        assert response.get_json()["feedback"]["short_feedback"] == "Good effort."
    turns = WritingTurn.query.filter_by(session_id=session_id).order_by(WritingTurn.turn_number).all()
    assert [turn.user_response for turn in turns] == ["I goes to school.", "I go to school.", "I go to school every day."]
    assert {turn.ai_prompt for turn in turns} == {"Write about your school."}


def test_without_asking_to_rewrite_a_second_submission_is_still_refused(client, auth_headers, monkeypatch):
    monkeypatch.setattr(groq_service, "evaluate_writing_answer", _feedback)
    session_id = _session(auth_headers)
    assert _submit(client, auth_headers, session_id, "First.").status_code == 200
    assert _submit(client, auth_headers, session_id, "Second.").status_code == 409
