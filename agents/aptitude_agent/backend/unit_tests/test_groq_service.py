import json
from types import SimpleNamespace

from flask import Flask

from backend.app.services import ai_service as groq_service


def test_json_completion_sets_configured_completion_budget(monkeypatch):
    app=Flask(__name__)
    app.config.update(OPENAI_JSON_MAX_COMPLETION_TOKENS=4096)
    captured={}

    class Completions:
        @staticmethod
        def create(**options):
            captured.update(options)
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps({"questions":[]})))],
                usage=SimpleNamespace(prompt_tokens=10,completion_tokens=5,total_tokens=15),
            )

    fake_client=SimpleNamespace(chat=SimpleNamespace(completions=Completions()))

    def complete(request_builder,**_options):
        return request_builder(fake_client,"openai/gpt-oss-20b"),"openai/gpt-oss-20b",{"provider_wait_ms":1,"provider_retry_count":0,"provider_attempt_count":1}

    monkeypatch.setattr(groq_service,"_complete",complete)

    with app.app_context():
        payload,usage=groq_service.json_completion("system","prompt")

    assert payload=={"questions":[]}
    assert usage["total_tokens"]==15
    assert captured["max_tokens"]==4096
    assert "reasoning_format" not in captured
    assert captured["response_format"]=={"type":"json_object"}


def test_text_completion_sets_low_reasoning_effort(monkeypatch):
    app=Flask(__name__)
    captured={}

    class Completions:
        @staticmethod
        def create(**options):
            captured.update(options)
            return SimpleNamespace(
                choices=[SimpleNamespace(
                    message=SimpleNamespace(content="Use short daily drills."),
                    finish_reason="stop",
                )],
                usage=SimpleNamespace(prompt_tokens=10,completion_tokens=5,total_tokens=15),
            )

    fake_client=SimpleNamespace(chat=SimpleNamespace(completions=Completions()))

    def complete(request_builder,**_options):
        return request_builder(fake_client,"openai/gpt-oss-20b"),"openai/gpt-oss-20b",{"provider_wait_ms":1,"provider_retry_count":0,"provider_attempt_count":1}

    monkeypatch.setattr(groq_service,"_complete",complete)
    with app.app_context():
        text,_usage=groq_service.text_completion(
            "system","prompt",maximum_tokens=512,reasoning_effort="low",
        )

    assert text=="Use short daily drills."
    assert captured["max_tokens"]==512
    assert "reasoning_format" not in captured
    assert "reasoning_effort" not in captured


def test_rate_limit_fails_over_without_retrying_same_model(monkeypatch):
    app=Flask(__name__)
    app.config.update(
        OPENAI_API_KEY="test",OPENAI_MODEL="primary",OPENAI_FALLBACK_MODELS=("fallback",),
        OPENAI_TIMEOUT_SECONDS=6,OPENAI_CIRCUIT_FAILURE_THRESHOLD=5,OPENAI_CIRCUIT_COOLDOWN_SECONDS=60,
    )
    calls=[]

    class RateLimitError(Exception):
        status_code=429
        response=SimpleNamespace(headers={"retry-after":"30"})

    class Completions:
        @staticmethod
        def create(**options):
            calls.append(options["model"])
            if options["model"]=="primary":raise RateLimitError("limited")
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="OK"))],
                usage=SimpleNamespace(prompt_tokens=1,completion_tokens=1,total_tokens=2),
            )

    created=[]
    def fake_groq(**options):
        created.append(options)
        return SimpleNamespace(chat=SimpleNamespace(completions=Completions()))

    monkeypatch.setattr(groq_service,"OpenAI",fake_groq)
    groq_service._circuits.clear()
    with app.app_context():
        text,usage=groq_service.text_completion("system","prompt")

    assert text=="OK"
    assert calls==["primary","fallback"]
    assert all(options["max_retries"]==0 for options in created)
    assert usage["provider_retry_count"]==0
    assert usage["provider_attempt_count"]==2


def test_later_request_honors_recorded_retry_after_before_calling_again(monkeypatch):
    app=Flask(__name__)
    app.config.update(
        OPENAI_API_KEY="test",OPENAI_MODEL="primary",OPENAI_FALLBACK_MODELS=("fallback",),
        OPENAI_TIMEOUT_SECONDS=6,OPENAI_CIRCUIT_FAILURE_THRESHOLD=5,OPENAI_CIRCUIT_COOLDOWN_SECONDS=60,
    )
    clock={"now":100.0};calls=[];model_calls={"primary":0,"fallback":0};sleeps=[]

    class RateLimitError(Exception):
        status_code=429
        def __init__(self,model):
            super().__init__("limited")
            self.response=SimpleNamespace(headers={"retry-after":"2" if model=="primary" else "1"})

    class Completions:
        @staticmethod
        def create(**options):
            model=options["model"];calls.append(model);model_calls[model]+=1
            if model_calls[model]==1:raise RateLimitError(model)
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="OK"))],
                usage=SimpleNamespace(prompt_tokens=1,completion_tokens=1,total_tokens=2),
            )

    monkeypatch.setattr(groq_service,"OpenAI",lambda **_options:SimpleNamespace(chat=SimpleNamespace(completions=Completions())))
    monkeypatch.setattr(groq_service.time,"monotonic",lambda:clock["now"])
    def fake_sleep(seconds):
        sleeps.append(seconds);clock["now"]+=seconds
    monkeypatch.setattr(groq_service.time,"sleep",fake_sleep)
    groq_service._circuits.clear()

    with app.app_context():
        try:
            groq_service.text_completion("system","prompt",deadline=clock["now"]+3)
            assert False,"the first request should expose the two provider 429s"
        except groq_service.AIProviderError as exc:
            assert exc.kind=="rate_limit"
            assert exc.provider_attempt_count==2
            assert exc.provider_retry_count==0
        text,usage=groq_service.text_completion("system","prompt",deadline=clock["now"]+3)

    assert text=="OK"
    assert calls==["primary","fallback","fallback"]
    assert len(sleeps)==1 and 1.0<=sleeps[0]<=1.2
    assert usage["provider_attempt_count"]==1


def test_json_validation_failure_gets_one_bounded_same_model_retry(monkeypatch):
    app=Flask(__name__)
    app.config.update(
        OPENAI_API_KEY="test",OPENAI_MODEL="primary",OPENAI_FALLBACK_MODELS=(),
        OPENAI_TIMEOUT_SECONDS=6,OPENAI_JSON_MAX_COMPLETION_TOKENS=512,
        OPENAI_CIRCUIT_FAILURE_THRESHOLD=5,OPENAI_CIRCUIT_COOLDOWN_SECONDS=60,
    )
    calls=[]

    class BadRequestError(Exception):
        status_code=400
        response=SimpleNamespace(headers={})

    class Completions:
        @staticmethod
        def create(**options):
            calls.append(options["model"])
            if len(calls)==1:
                raise BadRequestError("code: json_validate_failed; generated output was not valid JSON")
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps({"questions":[]})))],
                usage=SimpleNamespace(prompt_tokens=2,completion_tokens=2,total_tokens=4),
            )

    monkeypatch.setattr(
        groq_service,"OpenAI",
        lambda **_options:SimpleNamespace(chat=SimpleNamespace(completions=Completions())),
    )
    groq_service._circuits.clear()

    with app.app_context():
        payload,usage=groq_service.json_completion("system","prompt")

    assert payload=={"questions":[]}
    assert calls==["primary","primary"]
    assert usage["provider_retry_count"]==1
    assert usage["provider_attempt_count"]==2
    assert groq_service._circuits.get("primary",{}).get("failures",0)==0
