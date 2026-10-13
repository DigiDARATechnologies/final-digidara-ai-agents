"""Boss remembers each learner's earlier conversations (mem0)."""
import json
import time

from app.auth import service as auth_service
from app.orchestrator import boss_memory, graph, prompts
from app.orchestrator import routes as chat_routes

from test_phase2 import auth
from test_phase2_memory_voice import api  # noqa: F401  (fixture)


class FakeStore:
    def __init__(self, memories=None, delay=0.0):
        self.memories = list(memories or [])
        self.delay = delay
        self.added = []
        self.forgotten = []

    def recall(self, key, query, limit=5):
        time.sleep(self.delay)
        return [f"{key}: {m}" for m in self.memories][:limit]

    def remember(self, key, messages):
        self.added.append((key, messages))

    def all(self, key):
        return [f"{key}: {m}" for m in self.memories]

    def forget(self, key):
        self.forgotten.append(key)


def _stream_once(monkeypatch, reply="I'm Boss!"):
    monkeypatch.setattr(graph, "load_registry_node", lambda state: {"tools": [], "agents": []})
    seen = {}

    def fake_stream(system, user, tools, history, max_tokens):
        seen["system"] = system
        yield "text", reply

    monkeypatch.setattr(graph, "stream_with_tools", fake_stream)
    return seen


def test_boss_answers_with_what_it_remembers_and_remembers_the_new_turn(api, monkeypatch):  # noqa: F811
    store = FakeStore(["Asked in Tamil who Boss is; wants answers in English"])
    monkeypatch.setattr(boss_memory, "_store", store)
    seen = _stream_once(monkeypatch, "You asked who I am. I'm Boss!")
    api.app.include_router(chat_routes.router)
    response = api.post("/chat/route/stream", headers=auth(), json={"message": "What did I ask you last time?"})
    events = [json.loads(line[6:]) for line in response.text.split("\n\n") if line.startswith("data: ")]
    assert events[-1]["reply"] == "You asked who I am. I'm Boss!"
    assert "from_earlier_conversations_with_you" in seen["system"]
    assert "boss:learner: Asked in Tamil who Boss is" in seen["system"]
    assert store.added == [("boss:learner", [
        {"role": "user", "content": "What did I ask you last time?"},
        {"role": "assistant", "content": "You asked who I am. I'm Boss!"},
    ])]


def test_a_slow_memory_never_holds_up_the_reply(monkeypatch):
    monkeypatch.setattr(boss_memory, "_store", FakeStore(["something"], delay=3))
    monkeypatch.setattr(boss_memory, "RECALL_SECONDS", 0.2)
    started = time.perf_counter()
    assert boss_memory.recall("learner", "hello") == []
    assert time.perf_counter() - started < 1


def test_questions_about_the_conversation_itself_are_in_scope():
    prompt = prompts.router_system_prompt(has_tools=True)
    assert "what the learner asked earlier" in prompt and "never invent past questions" in prompt


def test_boss_memories_are_exported_and_erased_with_the_account(api, monkeypatch):  # noqa: F811
    store = FakeStore(["Wants to be a data analyst"])
    monkeypatch.setattr(boss_memory, "_store", store)
    exported = auth_service.export_user_data("learner")
    assert exported["boss_memory"] == ["boss:learner: Wants to be a data analyst"]
    auth_service.delete_user("learner")
    assert store.forgotten == ["boss:learner"]
