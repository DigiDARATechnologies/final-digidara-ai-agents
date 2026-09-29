"""The conversational chat turn (with mem0 memory) and lenient date parsing."""
import json
from datetime import date

import pytest

from app.routes import ai, chat_turn, resumes
from app.services import memory


@pytest.mark.parametrize("text,expected", [
    ("janm2022", date(2022, 1, 1)),
    ("Jan2022", date(2022, 1, 1)),
    ("jan-2022", date(2022, 1, 1)),
    ("Sept 2022", date(2022, 9, 1)),
    ("01/2022", date(2022, 1, 1)),
    ("2022-01", date(2022, 1, 1)),
    ("March, 2021", date(2021, 3, 1)),
    ("2022-03-15", date(2022, 3, 15)),
])
def test_everyday_dates_and_small_typos_are_understood(text, expected):
    assert resumes.parse_date(text) == expected


def test_an_unreadable_date_names_the_entry_to_fix():
    with pytest.raises(ValueError) as error:
        resumes.parse_date("sometime", "start date for Infosys")
    assert "start date for Infosys 'sometime'" in str(error.value)
    assert "Jan 2022" in str(error.value)


def test_creating_a_resume_with_a_typo_date_no_longer_fails(client, sample_resume_payload):
    sample_resume_payload["experience"][0]["start_date"] = "janm2022"
    sample_resume_payload["experience"][0]["end_date"] = "Present"
    response = client.post("/api/resumes", json=sample_resume_payload, headers={"X-User-Id": "test-user"})
    assert response.status_code == 201, response.get_json()


def ask(client, **payload):
    body = {"message": "hi", "step": "confirming", "draft": {}, "history": [], "user_id": "test-user", **payload}
    return client.post("/api/ai/chat-turn", json=body, headers={"X-User-Id": "test-user"})


def fake_model(monkeypatch, answer, prompts=None):
    def respond(prompt, max_tokens):
        if prompts is not None:
            prompts.append(prompt)
        return json.dumps(answer)
    monkeypatch.setattr(ai, "get_ai_response_text", respond)


def test_ug_and_pg_in_one_message_become_two_clean_entries(client, monkeypatch):
    fake_model(monkeypatch, {
        "intent": "answer",
        "updates": {"education": [
            {"school": "Nandha College", "degree": "B.Com", "level": "UG", "start_date": "2019", "end_date": "2022"},
            {"school": "KSR College", "degree": "M.Com", "level": "PG", "start_date": "2022", "end_date": "2024", "cgpa": "8.5"},
            {"degree": "MBA", "level": "PG"},
        ]},
        "reply": "Added your B.Com and M.Com.",
    })
    body = ask(client, message="UG - B.Com Nandha College 2019-2022; PG - M.Com KSR College 2022-2024 CGPA 8.5", step="awaiting_education").get_json()
    assert body["intent"] == "answer"
    # The entry with no college is dropped rather than saved half-empty.
    assert [entry["degree"] for entry in body["updates"]["education"]] == ["B.Com", "M.Com"]
    assert body["updates"]["education"][1]["cgpa"] == "8.5"


def test_an_edit_fixes_a_typo_date_and_unknown_fields_are_ignored(client, monkeypatch):
    fake_model(monkeypatch, {
        "intent": "edit",
        "updates": {
            "experience": [{"company": "Infosys", "role": "Intern", "start_date": "janm2022", "end_date": "june 2022"}],
            "salary": "10 LPA",
            "experienceLevel": "genius",
        },
        "reply": "Fixed the start date to Jan 2022.",
    })
    body = ask(client, message="the start date is jan 2022").get_json()
    assert body["updates"] == {"experience": [{"company": "Infosys", "role": "Intern", "start_date": "Jan 2022", "end_date": "Jun 2022"}]}
    assert body["reply"] == "Fixed the start date to Jan 2022."


def test_a_question_never_changes_the_draft(client, monkeypatch):
    fake_model(monkeypatch, {"intent": "question", "updates": {"name": "Someone Else"}, "reply": "CGPA is your grade point average."})
    body = ask(client, message="what is cgpa?").get_json()
    assert body["intent"] == "question"
    assert body["updates"] == {}


def test_memories_are_recalled_into_the_prompt_and_the_turn_is_remembered(client, monkeypatch):
    prompts, remembered = [], []
    monkeypatch.setattr(memory, "recall", lambda user_id, query: ["PG is MCA at KSR College, 2022-2024"])
    monkeypatch.setattr(memory, "remember", lambda user_id, messages: remembered.append((user_id, messages)))
    fake_model(monkeypatch, {"intent": "edit", "updates": {"summary": "MCA graduate."}, "reply": "Updated your summary."}, prompts)
    body = ask(client, message="mention my PG in the summary", draft={"name": "Prem"}).get_json()
    assert body["memories_used"] == 1
    assert "PG is MCA at KSR College, 2022-2024" in prompts[0]
    assert '"name": "Prem"' in prompts[0]
    assert remembered == [("test-user", [
        {"role": "user", "content": "mention my PG in the summary"},
        {"role": "assistant", "content": "Updated your summary."},
    ])]


def test_memory_is_off_unless_enabled(monkeypatch):
    monkeypatch.delenv("MEM0_ENABLED", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "key")
    assert memory.memory_enabled() is False
    assert memory.recall("test-user", "anything") == []
    memory.remember("test-user", [{"role": "user", "content": "hello"}])  # no error, nothing to do


def test_a_broken_memory_backend_never_breaks_the_chat(monkeypatch):
    class Broken:
        def search(self, *args, **kwargs):
            raise ConnectionError("qdrant is down")
    monkeypatch.setattr(memory, "_memory", lambda: Broken())
    assert memory.recall("test-user", "anything") == []


def test_memory_search_is_scoped_to_the_user(monkeypatch):
    calls = []

    class Recorder:
        def search(self, query, **kwargs):
            calls.append((query, kwargs))
            return {"results": [{"memory": "Name is Prem"}, {"memory": ""}]}
    monkeypatch.setattr(memory, "_memory", lambda: Recorder())
    assert memory.recall("user-1", "what is my name") == ["Name is Prem"]
    assert calls == [("what is my name", {"top_k": 8, "filters": {"user_id": "user-1"}})]


def test_the_chat_turn_is_reachable_through_invoke(client, monkeypatch):
    fake_model(monkeypatch, {"intent": "edit", "updates": {"phone": "9876543210"}, "reply": "Updated your phone."})
    response = client.post("/api/invoke", json={"action": "resume_chat_turn", "payload": {
        "user_id": "test-user", "message": "my phone is 9876543210", "step": "confirming", "draft": {}, "history": [],
    }})
    assert response.status_code == 200
    assert response.get_json()["updates"] == {"phone": "9876543210"}


def test_an_empty_message_is_rejected(client):
    assert ask(client, message="  ").status_code == 400


def test_model_failure_is_reported_not_crashed(client, monkeypatch):
    def fail(prompt, max_tokens):
        raise RuntimeError("AI provider is not configured")
    monkeypatch.setattr(ai, "get_ai_response_text", fail)
    response = ask(client, message="change my name")
    assert response.status_code == 502
    assert "AI provider is not configured" in response.get_json()["message"]
