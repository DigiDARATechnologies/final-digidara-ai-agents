"""Boss's small repairs: code decides whether each runs, not the model."""
import asyncio
from types import SimpleNamespace

from app import db
from app.learner import service as learner_service
from app.links import service as links_service
from app.models import BossIssueReport, Conversation
from app.orchestrator import repairs
from app.readiness import service as readiness_service

from test_phase2 import auth
from test_phase2_memory_voice import api  # noqa: F401  (fixture)

USER = SimpleNamespace(id="learner", email="learner@example.test")
ASKED_EXIT = [{"role": "assistant", "content": "Should I exit your interview?"}]


def _run(action, message="", history=None):
    return asyncio.run(repairs.run(USER, action, message, history or []))


def _interview(monkeypatch, active, status=200):
    calls = []

    async def fake(user, action, payload=None):
        calls.append((action, payload or {}))
        if action == "ensure_session":
            return 200, {"sessionToken": "tok"}
        if action == "active_interview":
            return status, active
        return 200, {"question": "Next?"}

    monkeypatch.setattr(repairs, "_interview_call", fake)
    return calls


STALLED = {"active": False, "needs_next_question": True, "interview_id": 9, "round_type": "technical", "subject": "SQL",
           "interview_mode": "custom_topic", "difficulty": "beginner", "num_questions": 5, "role_name": None}


def test_a_stalled_interview_continues_with_its_own_settings_and_opens(monkeypatch):
    calls = _interview(monkeypatch, STALLED, 409)
    result = _run({"type": "fix", "name": "interview_continue"})
    assert result["ok"] and result["open"] == "mock-interview"
    action, payload = calls[-1]
    assert action == "start_interview" and payload["subject"] == "SQL" and payload["num_questions"] == 5
    assert payload["sessionToken"] == "tok" and "role_name" not in payload


def test_a_role_interview_resumes_with_its_stored_subjects_and_any_stored_length(monkeypatch):
    calls = _interview(monkeypatch, {**STALLED, "interview_mode": "role", "role_name": "Data Analyst", "subject": "sql",
                                     "resolved_subjects": '["sql", "excel"]', "num_questions": 3}, 409)
    assert _run({"type": "fix", "name": "interview_continue"})["ok"]
    payload = calls[-1][1]
    assert payload["resolved_subjects"] == ["sql", "excel"] and payload["num_questions"] == 5


def test_nothing_runs_when_the_interview_is_not_in_that_state(monkeypatch):
    calls = _interview(monkeypatch, {"active": False})
    assert not _run({"type": "fix", "name": "interview_continue"})["ok"]
    assert not _run({"type": "fix", "name": "interview_report"})["ok"]
    assert all(action in ("ensure_session", "active_interview") for action, _ in calls)


def test_a_report_runs_only_when_every_answer_is_in(monkeypatch):
    calls = _interview(monkeypatch, {"active": False, "awaiting_report": True, "interview_id": 9}, 409)
    assert _run({"type": "fix", "name": "interview_report"})["ok"]
    assert calls[-1] == ("end_interview", {"interview_id": 9, "sessionToken": "tok"})


def test_exiting_needs_the_learners_yes(monkeypatch):
    calls = _interview(monkeypatch, {"active": True, "interview_id": 9, "question_order": 2})
    # The model wrote the tag on its own (say, from text hidden on the page).
    assert not _run({"type": "fix", "name": "interview_exit"}, "What is SQL?", ASKED_EXIT)["ok"]
    assert not _run({"type": "fix", "name": "interview_exit"}, "yes", [{"role": "assistant", "content": "Want a hint?"}])["ok"]
    assert not calls
    assert _run({"type": "fix", "name": "interview_exit"}, "yes please", ASKED_EXIT)["ok"]
    assert calls[-1][0] == "exit_interview"


def test_a_level_switches_only_when_open_asked_for_and_not_set_by_the_organization(api, monkeypatch):  # noqa: F811
    action = {"type": "level", "agent": "codeforge_agent", "level": "medium"}
    monkeypatch.setattr(readiness_service, "open_levels_for", lambda user, agent: ["beginner"])
    assert "not open" in _run(action, "switch me to medium")["text"]
    monkeypatch.setattr(readiness_service, "open_levels_for", lambda user, agent: ["beginner", "medium"])
    assert "Nothing was changed" in _run(action, "what is my score?")["text"]
    assert learner_service.get_levels("learner")["codeforge_agent"]["level"] == "beginner"
    assert _run(action, "switch me to medium")["ok"]
    assert learner_service.get_levels("learner")["codeforge_agent"]["level"] == "medium"
    learner_service.set_level("learner", "codeforge_agent", "beginner", "organization")
    assert "organization" in _run(action, "switch me to medium")["text"]
    assert learner_service.get_levels("learner")["codeforge_agent"]["level"] == "beginner"


def test_a_report_keeps_only_what_the_learner_said_and_has_a_daily_limit(api):  # noqa: F811
    action = {"type": "report", "category": "interview"}
    assert "Nothing was sent" in _run(action, "why is this slow?")["text"]
    asked = [{"role": "user", "content": "My interview report never loads"},
             {"role": "assistant", "content": "Should I report this to the SkillDARA team?"}]
    assert _run(action, "yes", asked)["ok"]
    session = db.get_session()
    row = session.query(BossIssueReport).filter_by(user_id="learner").one()
    assert row.message == "My interview report never loads" and row.category == "interview"
    session.close()
    for _ in range(repairs.REPORTS_PER_DAY - 1):
        assert _run(action, "report this please")["ok"]
    assert not _run(action, "report this please")["ok"]


def test_cancelling_links_touches_only_this_learners_chat(api):  # noqa: F811
    from datetime import datetime

    session = db.get_session()
    now = datetime.utcnow()
    session.add(Conversation(id="repair-chat", user_id="learner", agent_id="aptitude", title="T", created_at=now,
                             updated_at=now, updated_at_ms=1))
    session.commit()
    session.close()
    link = links_service.create_chat_link("learner", "repair-chat", "public")
    token = link["path"].rsplit("/", 1)[1]
    assert links_service.remove_chat_links("someone-else", "repair-chat") == 0
    assert links_service.read_shared_chat(token, "learner")["is_owner"] is True
    assert _run({"type": "unshare", "chat_id": "repair-chat"})["ok"]
    assert "no links" in _run({"type": "unshare", "chat_id": "repair-chat"})["text"]


def test_a_failing_repair_says_so_and_never_raises(monkeypatch):
    async def broken(user, action, payload=None):
        raise RuntimeError("agent down")

    monkeypatch.setattr(repairs, "_interview_call", broken)
    assert _run({"type": "fix", "name": "interview_continue"})["ok"] is False
