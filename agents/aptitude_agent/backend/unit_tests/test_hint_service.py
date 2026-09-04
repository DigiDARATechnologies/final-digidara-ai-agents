from types import SimpleNamespace

from flask import Flask

from backend.app.services.hint_service import TOPIC_HINTS, generate_hint


def test_hint_uses_deterministic_fallback_without_groq():
    app=Flask(__name__)
    app.config.update(GROQ_API_KEY="")
    question=SimpleNamespace(topic="Time & Work")

    with app.app_context():
        hint,usage=generate_hint(question)

    assert hint==TOPIC_HINTS["Time & Work"]
    assert usage["model"]=="deterministic-fallback"
    assert usage["fallback"] is True
