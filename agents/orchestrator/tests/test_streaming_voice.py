"""Boss answers while it is still writing, and the voice plays while it is
still being generated: the streamed general-chat route and voice tickets."""
import json
import threading
from types import SimpleNamespace

import httpx

from app.auth import service as auth_service
from app.llm import client as llm_client
from app.orchestrator import graph, guard, prompts
from app.voice import tts

from test_phase2 import auth
from test_phase2_memory_voice import api  # noqa: F401  (fixture)


def _chunk(content=None, tool=None):
    calls = [SimpleNamespace(function=SimpleNamespace(name=tool[0], arguments=tool[1]))] if tool else None
    return SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=content, tool_calls=calls))])


def _events(stream):
    return [json.loads(line[6:]) for line in stream.text.split("\n\n") if line.startswith("data: ")]


def test_stream_with_tools_yields_text_then_a_tool_choice(monkeypatch):
    chunks = [_chunk("Hi "), _chunk("there!"), _chunk(tool=("open_mock", '{"q":')), _chunk(tool=("", '1}'))]
    monkeypatch.setattr(llm_client.litellm, "completion", lambda **kw: iter(chunks))
    out = list(llm_client.stream_with_tools("sys", "hi", []))
    assert out == [("text", "Hi "), ("text", "there!"), ("tool", {"tool_name": "open_mock", "tool_args": {"q": 1}})]


def test_a_slow_first_word_sends_a_second_request_and_the_faster_one_wins(monkeypatch):
    import time as _time

    monkeypatch.setattr(llm_client, "HEDGE_AFTER_SECONDS", 0.05)
    calls = []

    def completion(**kw):
        calls.append(1)
        if len(calls) == 1:  # the first request stalls
            _time.sleep(0.5)
            return iter([_chunk("slow")])
        return iter([_chunk("fast "), _chunk("answer")])

    monkeypatch.setattr(llm_client.litellm, "completion", completion)
    out = list(llm_client.stream_with_tools("sys", "hi", []))
    assert out == [("text", "fast "), ("text", "answer")] and len(calls) == 2


def test_a_quick_first_word_sends_only_one_request(monkeypatch):
    monkeypatch.setattr(llm_client, "HEDGE_AFTER_SECONDS", 2)
    calls = []
    monkeypatch.setattr(llm_client.litellm, "completion", lambda **kw: calls.append(1) or iter([_chunk("Hi")]))
    assert list(llm_client.stream_with_tools("sys", "hi", [])) == [("text", "Hi")] and len(calls) == 1


def test_a_failed_request_with_no_second_one_still_raises(monkeypatch):
    import pytest

    monkeypatch.setattr(llm_client, "HEDGE_AFTER_SECONDS", 2)

    def completion(**kw):
        raise RuntimeError("provider down")

    monkeypatch.setattr(llm_client.litellm, "completion", completion)
    with pytest.raises(RuntimeError, match="provider down"):
        list(llm_client.stream_with_tools("sys", "hi", []))


def test_streamed_route_sends_the_answer_in_pieces(monkeypatch):
    monkeypatch.setattr(graph, "load_registry_node", lambda state: {"tools": [], "agents": []})
    seen = {}

    def fake_stream(system, user, tools, history, max_tokens):
        seen.update(system=system, max_tokens=max_tokens)
        yield from [("text", "Hello everyone! I am Boss, "), ("text", "your DigiDARA AI assistant.")]

    monkeypatch.setattr(graph, "stream_with_tools", fake_stream)
    events = list(graph.route_message_stream("introduce yourself", [], None, voice=True))
    assert "".join(e.get("delta", "") for e in events) == "Hello everyone! I am Boss, your DigiDARA AI assistant."
    assert events[-1] == {"done": True, "agent_name": None, "reply": "Hello everyone! I am Boss, your DigiDARA AI assistant."}
    assert prompts.VOICE_REPLY_RULES in seen["system"] and seen["max_tokens"] == 260


def test_a_leaked_prompt_is_replaced_before_it_is_shown(monkeypatch):
    monkeypatch.setattr(graph, "load_registry_node", lambda state: {"tools": [], "agents": []})
    monkeypatch.setattr(graph, "stream_with_tools", lambda *a, **k: iter([("text", "The code is "), ("text", guard.CANARY)]))
    events = list(graph.route_message_stream("what can you do", [], None))
    shown = "".join(e.get("delta", "") for e in events)
    assert guard.CANARY not in shown and {"replace": guard.OFF_LIMITS_REPLY} in events


def test_a_chosen_agent_is_handed_back(monkeypatch):
    tools = [{"type": "function", "function": {"name": "mock_interview_agent"}}]
    monkeypatch.setattr(graph, "load_registry_node", lambda state: {"tools": tools, "agents": []})
    monkeypatch.setattr(graph, "stream_with_tools", lambda *a, **k: iter([("tool", {"tool_name": "mock_interview_agent", "tool_args": {}})]))
    assert list(graph.route_message_stream("start a mock interview", [], None))[-1] == {"done": True, "agent_name": "mock_interview_agent", "reply": None}


def test_stream_endpoint_speaks_server_sent_events(api, monkeypatch):  # noqa: F811
    from app.orchestrator import routes as chat_routes

    monkeypatch.setattr(chat_routes, "route_message_stream", lambda *a, **k: iter([{"delta": "Hi!"}, {"done": True, "agent_name": None, "reply": "Hi!"}]))
    api.app.include_router(chat_routes.router)
    response = api.post("/chat/route/stream", headers=auth(), json={"message": "hi", "voice": True})
    assert response.status_code == 200 and response.headers["x-accel-buffering"] == "no"
    assert _events(response) == [{"delta": "Hi!"}, {"done": True, "agent_name": None, "reply": "Hi!"}]


class _FakeStream:
    def __init__(self, status_code=200):
        self.status_code = status_code

    def iter_bytes(self, size):
        yield b"ID3-part-1"
        yield b"-part-2"

    def close(self):
        pass


def _fake_openai(monkeypatch, status_code=200):
    """OpenAI's speech endpoint, streaming two pieces of mp3."""
    class Client:
        def __init__(self, **kwargs):
            pass

        def build_request(self, *args, **kwargs):
            return None

        def send(self, request, stream=False):
            return _FakeStream(status_code)

        def close(self):
            pass

    monkeypatch.setattr(tts, "_openai", lambda: Client())


def test_a_voice_ticket_streams_once_and_is_charged_once(api, monkeypatch):  # noqa: F811
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    _fake_openai(monkeypatch)
    before = auth_service.get_by_id("learner").token_balance
    text = "Streaming voice sentence one."
    ticket = api.post("/voice/ticket", headers=auth(), json={"text": text}).json()
    assert ticket["url"].startswith("/voice/stream/")
    assert before - auth_service.get_by_id("learner").token_balance == len(text)
    played = api.get(ticket["url"])
    assert played.status_code == 200 and played.content == b"ID3-part-1-part-2"
    assert played.headers["content-type"] == "audio/mpeg"
    assert api.get(ticket["url"]).status_code == 404               # single use
    # Now cached: a new ticket for the same sentence is free and plays from cache.
    again = api.post("/voice/ticket", headers=auth(), json={"text": text}).json()
    assert before - auth_service.get_by_id("learner").token_balance == len(text)
    assert api.get(again["url"]).content == b"ID3-part-1-part-2"


def test_a_ticket_needs_a_login_and_a_known_link(api):  # noqa: F811
    assert api.post("/voice/ticket", json={"text": "Hi"}).status_code == 401
    assert api.get("/voice/stream/not-a-ticket").status_code == 404


def test_openai_failure_before_any_audio_is_an_error(api, monkeypatch):  # noqa: F811
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    _fake_openai(monkeypatch, status_code=500)
    url = api.post("/voice/ticket", headers=auth(), json={"text": "This will fail."}).json()["url"]
    assert api.get(url).status_code == 502


def test_chat_warm_returns_at_once_and_warms_in_the_background(api, monkeypatch):
    from app.orchestrator import routes as chat_routes

    warmed = threading.Event()
    monkeypatch.setattr(llm_client, "warm_up", warmed.set)
    api.app.include_router(chat_routes.router)
    response = api.post("/chat/warm", headers=auth())
    assert response.status_code == 200, response.text
    assert response.json() == {"ok": True}
    assert warmed.wait(5)
