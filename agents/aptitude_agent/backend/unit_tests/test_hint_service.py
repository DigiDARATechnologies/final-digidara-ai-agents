from types import SimpleNamespace

from flask import Flask

from backend.app.services import hint_service
from backend.app.services.hint_service import HintUnavailable, TOPIC_HINTS, generate_hint


def test_hint_uses_deterministic_fallback_without_provider():
    app=Flask(__name__)
    app.config.update(OPENAI_API_KEY="")
    question=SimpleNamespace(topic="Time & Work")

    with app.app_context():
        hint,usage=generate_hint(question)

    assert hint==TOPIC_HINTS["Time & Work"]
    assert usage["model"]=="deterministic-fallback"
    assert usage["fallback"] is True


def test_hint_prompt_contains_only_current_question_context(monkeypatch):
    captured=[]
    question=SimpleNamespace(
        category="Computer Fundamentals",topic="Operating Systems",difficulty="Easy",
        question_text="Which component coordinates core operating-system resources?",
        options={"A":"Kernel","B":"Browser","C":"Editor","D":"Spreadsheet"},
        correct_answer="A",
    )

    def completion(system,prompt,temperature,**options):
        captured.append((system,prompt,temperature,options))
        return {"hint":"Focus on the component responsible for coordinating core system resources."},{
            "input_tokens":20,"output_tokens":9,"total_tokens":29,
            "provider_attempt_count":1,"model":"hint-model",
        }

    monkeypatch.setattr(hint_service,"json_completion",completion)
    app=Flask(__name__)
    app.config.update(
        OPENAI_API_KEY="test",OPENAI_MODEL="hint-model",OPENAI_FALLBACK_MODELS=(),
        HINT_TIMEOUT_SECONDS=5,HINT_MAX_COMPLETION_TOKENS=96,
    )
    with app.app_context():
        hint,usage=generate_hint(question)

    system,prompt,temperature,options=captured[0]
    assert hint.startswith("Focus on")
    assert temperature==0
    assert options["maximum_tokens"]==96
    assert question.question_text in prompt
    assert question.category in prompt and question.topic in prompt
    assert "Kernel" not in prompt
    assert "previous" not in prompt.casefold()
    assert "history" not in prompt.casefold()
    assert "score" not in prompt.casefold()
    assert len(system)<450
    assert usage["total_tokens"]==29


def test_hint_validation_rejects_answer_and_option_disclosure():
    for unsafe in ("The answer is tuple.","Choose option B.","Focus on tuple because it cannot change."):
        try:
            hint_service._validate_hint(unsafe,"tuple")
        except HintUnavailable:
            pass
        else:
            raise AssertionError(f"Expected unsafe hint to be rejected: {unsafe}")
