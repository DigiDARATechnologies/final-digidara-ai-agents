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

    def fake_stream(system, user, tools, history, max_tokens, usage=None):
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


def test_a_brisk_voice_is_the_same_person_at_a_quicker_pace_and_cached_apart(api, monkeypatch):  # noqa: F811
    normal = tts.instructions_for("en")
    brisk = tts.instructions_for("en", "brisk")
    assert normal != brisk and "brisk" in brisk and "slowly" in normal and "slow teacher voice" in brisk
    assert "Nila" in brisk and "Indian English" in brisk          # same character and accent
    assert tts._cache_key("Hi", "en", "nova") != tts._cache_key("Hi", "en", "nova", "brisk")
    assert tts._cache_key("Hi", "en", "nova") == tts._cache_key("Hi", "en", "nova", "normal")

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    sent = []

    class Client:
        def build_request(self, method, url, headers=None, json=None):
            sent.append(json["instructions"])
            return None

        def send(self, request, stream=False):
            return _FakeStream()

    monkeypatch.setattr(tts, "_openai", lambda: Client())
    url = api.post("/voice/ticket", headers=auth(), json={"text": "Quick reply here.", "pace": "brisk"}).json()["url"]
    assert api.get(url).status_code == 200
    assert sent == [brisk]
    # An unknown pace is the normal voice.
    url = api.post("/voice/ticket", headers=auth(), json={"text": "Another reply here.", "pace": "warp"}).json()["url"]
    api.get(url)
    assert sent[-1] == normal


def test_a_stalled_voice_request_is_sent_again_instead_of_waiting(api, monkeypatch):  # noqa: F811
    # OpenAI sometimes sends nothing for half a minute; a fresh request answers at once.
    assert tts.TTS_TIMEOUT.read == tts.TTS_STALL_SECONDS < 10
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    sends = []

    class Client:
        def build_request(self, *args, **kwargs):
            return None

        def send(self, request, stream=False):
            sends.append(1)
            if len(sends) == 1:
                raise httpx.ReadTimeout("stalled")
            return _FakeStream()

    monkeypatch.setattr(tts, "_openai", lambda: Client())
    url = api.post("/voice/ticket", headers=auth(), json={"text": "A stalled sentence."}).json()["url"]
    played = api.get(url)
    assert played.status_code == 200 and played.content == b"ID3-part-1-part-2"
    assert len(sends) == 2

    stalls = []

    class Stalled:
        def build_request(self, *args, **kwargs):
            return None

        def send(self, request, stream=False):
            stalls.append(1)
            raise httpx.ReadTimeout("stalled")

    monkeypatch.setattr(tts, "_openai", lambda: Stalled())
    response = api.post("/voice/speak", headers=auth(), json={"text": "Never answered."})
    assert response.status_code == 502
    assert len(stalls) == tts.TTS_ATTEMPTS


def test_a_slow_voice_request_is_raced_by_a_second_one_instead_of_waited_out(api, monkeypatch):  # noqa: F811
    # About one OpenAI voice request in three sends nothing for 8 s or more.
    # After HEDGE_AFTER_SECONDS a second request is sent alongside, and the
    # first to start is played: the learner waits ~2 s, not the whole stall.
    import time

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr(tts, "HEDGE_AFTER_SECONDS", 0.2)
    release = threading.Event()
    closed = []

    class SlowStream(_FakeStream):
        def iter_bytes(self, size):
            release.wait(5)
            yield b"late"

        def close(self):
            closed.append(1)

    sends = []

    class Client:
        def build_request(self, *args, **kwargs):
            return None

        def send(self, request, stream=False):
            sends.append(1)
            return SlowStream() if len(sends) == 1 else _FakeStream()

    monkeypatch.setattr(tts, "_openai", lambda: Client())
    started = time.monotonic()
    url = api.post("/voice/ticket", headers=auth(), json={"text": "A slow sentence."}).json()["url"]
    played = api.get(url)
    assert played.content == b"ID3-part-1-part-2"
    assert time.monotonic() - started < 2 and len(sends) == 2
    release.set()
    for _ in range(50):
        if closed:
            break
        time.sleep(0.02)
    assert closed  # the slow loser is closed, not left open


def test_a_spoken_greeting_or_small_talk_gets_a_conversational_answer():
    rules = prompts.VOICE_REPLY_RULES
    assert "small talk" in rules and "not a description of DigiDARA" in rules
