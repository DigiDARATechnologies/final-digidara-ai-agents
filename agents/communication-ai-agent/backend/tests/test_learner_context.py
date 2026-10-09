"""Phase 2: practice topics fit the learner the gateway names."""
import json

from app.services import groq_common, learner_context

LEARNER = {
    "target_role": "AI Engineer", "skills": ["python", "llm"],
    "memory": [{"kind": "gap", "text": "Communication: Weak: fluency"}, {"kind": "strength", "text": "Coding: loops"}],
}


def _prompt_for(app, monkeypatch, body):
    seen = {}

    def fake_chat(system_prompt, user_prompt, **kwargs):
        seen["prompt"] = user_prompt
        topics = [{"title": f"Topic {i}", "description": "Talk about it", "expected_duration_seconds": 90} for i in range(6)]
        return json.dumps({"topics": topics})

    monkeypatch.setattr(groq_common, "_chat", fake_chat)
    token = learner_context.set_from_envelope(body)
    try:
        groq_common.generate_practice_topics("speaking", "topic_wise", "medium")
    finally:
        learner_context.reset(token)
    return seen["prompt"]


def test_topics_are_framed_for_the_learners_role(app, monkeypatch):
    prompt = _prompt_for(app, monkeypatch, {"action": "x", "learner": LEARNER})
    assert "preparing for a AI Engineer job (skills: python, llm)" in prompt
    assert "Communication: Weak: fluency" in prompt and "Coding: loops" not in prompt
    assert "Difficulty: medium" in prompt


def test_without_a_learner_the_prompt_is_unchanged(app, monkeypatch):
    prompt = _prompt_for(app, monkeypatch, {"action": "x"})
    assert "preparing for" not in prompt and "6." not in prompt
    assert learner_context.current() is None
