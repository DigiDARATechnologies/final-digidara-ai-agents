"""The general chat's microphone: POST /chat/transcribe sends the recording to
OpenAI and returns only the text."""
import base64
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.auth.security import create_access_token
from app.llm import transcribe as speech
from app.orchestrator.routes import router
from app.rate_limit import limiter

AUDIO = base64.b64encode(b"\x1a\x45\xdf\xa3fake-webm-audio").decode()


@pytest.fixture
def api(learner, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.include_router(router)
    limiter.reset()
    with TestClient(app) as client:
        yield client


def headers(user="learner"):
    return {"Authorization": "Bearer " + create_access_token(user)}


def openai_replies(monkeypatch, status=200, body=None):
    post = Mock(return_value=SimpleNamespace(status_code=status, json=lambda: body or {"text": "How do I use the capstone agent?"}))
    monkeypatch.setattr(speech.httpx, "post", post)
    return post


def test_a_recording_comes_back_as_text(api, monkeypatch):
    post = openai_replies(monkeypatch)
    response = api.post("/chat/transcribe", json={"audio_base64": AUDIO, "mime_type": "audio/webm;codecs=opus"}, headers=headers())
    assert response.status_code == 200 and response.json() == {"transcript": "How do I use the capstone agent?"}
    sent = post.call_args.kwargs
    assert sent["data"]["model"] == "gpt-4o-mini-transcribe"
    assert sent["files"]["file"][0] == "question.webm" and sent["files"]["file"][2] == "audio/webm"
    assert sent["headers"]["Authorization"] == "Bearer sk-test"


def test_it_needs_a_login(api, monkeypatch):
    post = openai_replies(monkeypatch)
    assert api.post("/chat/transcribe", json={"audio_base64": AUDIO}).status_code == 401
    post.assert_not_called()


@pytest.mark.parametrize("payload,status", [
    ({"audio_base64": AUDIO, "mime_type": "application/pdf"}, 400),       # not audio
    ({"audio_base64": "not base64!!", "mime_type": "audio/webm"}, 400),
    ({"audio_base64": "A" * (speech.MAX_AUDIO_BASE64_CHARS + 1)}, 422),    # too long a recording
])
def test_bad_recordings_never_reach_openai(api, monkeypatch, payload, status):
    post = openai_replies(monkeypatch)
    assert api.post("/chat/transcribe", json=payload, headers=headers()).status_code == status
    post.assert_not_called()


def test_an_openai_failure_is_a_clean_error_with_no_details(api, monkeypatch):
    openai_replies(monkeypatch, status=500, body={"error": {"message": "internal detail sk-test"}})
    response = api.post("/chat/transcribe", json={"audio_base64": AUDIO}, headers=headers())
    assert response.status_code == 502
    assert "sk-test" not in response.text and "internal detail" not in response.text


def test_without_an_openai_key_voice_is_unavailable(api, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY")
    post = openai_replies(monkeypatch)
    assert api.post("/chat/transcribe", json={"audio_base64": AUDIO}, headers=headers()).status_code == 503
    post.assert_not_called()


def test_it_is_rate_limited_per_user(api, monkeypatch):
    openai_replies(monkeypatch)
    codes = [api.post("/chat/transcribe", json={"audio_base64": AUDIO}, headers=headers()).status_code for _ in range(16)]
    assert codes[:15] == [200] * 15 and codes[15] == 429
