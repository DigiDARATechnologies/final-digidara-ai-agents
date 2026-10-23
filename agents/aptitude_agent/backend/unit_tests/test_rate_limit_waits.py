"""A 429 from OpenAI means "slow down for a moment". With hundreds of learners
starting a test at once, the request waits and retries instead of failing, and
one 429 no longer blocks the model for the 60-90 s outage cooldown."""
import importlib
from types import SimpleNamespace

import pytest
from flask import Flask

from backend.app.services import ai_service


def make_app(**overrides):
    app=Flask(__name__)
    app.config.update(
        OPENAI_API_KEY="test",OPENAI_MODEL="primary",OPENAI_FALLBACK_MODELS=(),
        OPENAI_TIMEOUT_SECONDS=6,OPENAI_CIRCUIT_FAILURE_THRESHOLD=5,OPENAI_CIRCUIT_COOLDOWN_SECONDS=90,
    )
    app.config.update(overrides)
    return app


class RateLimitError(Exception):
    status_code=429
    def __init__(self,headers):
        super().__init__("limited")
        self.response=SimpleNamespace(headers=headers)


def ok():
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="OK"))],
        usage=SimpleNamespace(prompt_tokens=1,completion_tokens=1,total_tokens=2),
    )


@pytest.fixture
def provider(monkeypatch):
    state=SimpleNamespace(now=100.0,sleeps=[],calls=[],failures=[])

    class Completions:
        @staticmethod
        def create(**options):
            state.calls.append(options["model"])
            if state.failures:
                raise RateLimitError(state.failures.pop(0))
            return ok()

    monkeypatch.setattr(ai_service,"OpenAI",lambda **_o:SimpleNamespace(chat=SimpleNamespace(completions=Completions())))
    monkeypatch.setattr(ai_service.time,"monotonic",lambda:state.now)
    def sleep(seconds):
        state.sleeps.append(seconds);state.now+=seconds
    monkeypatch.setattr(ai_service.time,"sleep",sleep)
    monkeypatch.setattr(ai_service.random,"uniform",lambda _a,_b:0.0)
    ai_service._circuits.clear()
    yield state
    ai_service._circuits.clear()


def test_a_rate_limited_call_waits_and_succeeds(provider):
    provider.failures=[{}]  # no Retry-After header at all
    with make_app().app_context():
        text,usage=ai_service.text_completion("system","prompt",deadline=provider.now+120)
    assert text=="OK"
    assert provider.calls==["primary","primary"]
    assert provider.sleeps==[pytest.approx(2.15)]  # 2 s default, not the 90 s outage cooldown
    assert usage["provider_retry_count"]==1


def test_retry_after_ms_is_honoured(provider):
    provider.failures=[{"retry-after-ms":"500"}]
    with make_app().app_context():
        ai_service.text_completion("system","prompt",deadline=provider.now+120)
    assert provider.sleeps==[pytest.approx(0.65)]


def test_a_huge_retry_after_is_capped(provider):
    provider.failures=[{"retry-after":"600"}]
    with make_app().app_context():
        ai_service.text_completion("system","prompt",deadline=provider.now+120)
    assert provider.sleeps==[pytest.approx(30.15)]


def test_persistent_rate_limiting_still_fails_after_three_waits(provider):
    provider.failures=[{"retry-after":"1"}]*10
    with make_app().app_context(),pytest.raises(ai_service.AIProviderError) as raised:
        ai_service.text_completion("system","prompt",deadline=provider.now+120)
    assert raised.value.kind=="rate_limit"
    assert len(provider.calls)==1+ai_service.RATE_LIMIT_ROUNDS
    assert len(provider.sleeps)==ai_service.RATE_LIMIT_ROUNDS


def test_no_wait_when_the_deadline_leaves_no_room_for_a_call(provider):
    provider.failures=[{"retry-after":"2"}]
    with make_app().app_context(),pytest.raises(ai_service.AIProviderError):
        ai_service.text_completion("system","prompt",deadline=provider.now+4)
    assert provider.sleeps==[]


def test_a_rate_limited_primary_fails_over_to_the_fallback_without_waiting(provider):
    provider.failures=[{"retry-after":"5"}]
    with make_app(OPENAI_FALLBACK_MODELS=("fallback",)).app_context():
        text,_usage=ai_service.text_completion("system","prompt",deadline=provider.now+120)
    assert text=="OK"
    assert provider.calls==["primary","fallback"]
    assert provider.sleeps==[]


@pytest.mark.parametrize("value,expected",[
    (None,("gpt-4.1-mini",)), ("",("gpt-4.1-mini",)), ("none",()), ("gpt-4.1-nano, gpt-4.1-mini",("gpt-4.1-nano","gpt-4.1-mini")),
])
def test_fallback_model_default(monkeypatch,value,expected):
    if value is None:
        monkeypatch.delenv("OPENAI_FALLBACK_MODELS",raising=False)
    else:
        monkeypatch.setenv("OPENAI_FALLBACK_MODELS",value)
    from backend.app import config
    try:
        assert importlib.reload(config).Config.OPENAI_FALLBACK_MODELS==expected
    finally:
        monkeypatch.delenv("OPENAI_FALLBACK_MODELS",raising=False)
        importlib.reload(config)
