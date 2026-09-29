import copy
from unittest.mock import MagicMock, patch

import pytest

from job_agent.chat_service import (
    _handle_onboarding_step, _profile_clarification, _profile_completion_status, chat_with_job_agent,
)


def profile(**overrides):
    return {"full_name": "", "skills": [], "preferred_titles": [], "preferred_locations": [],
            "preferred_work_mode": "", "experience_years": 0, "experience_provided": False,
            "profile_completed": 0, "onboarding_step": "full_name", **overrides}


@pytest.mark.parametrize("message", ["why you ask my name?", "what is the reason you need my name?",
                                     "Why do you need my full name?", "What do you use my nickname for?"])
def test_name_purpose_is_not_generic_yes_and_never_changes_profile(message):
    saved = profile()
    before = copy.deepcopy(saved)
    db, cursor = MagicMock(), MagicMock()
    db.cursor.return_value = cursor
    with (patch("job_agent.chat_service.get_db", return_value=db),
          patch("job_agent.chat_service._get_user_profile_and_missing", return_value=(saved, [])),
          patch("job_agent.chat_service._apply_profile_updates") as update,
          patch("job_agent.chat_service.requests.post") as llm):
        result = chat_with_job_agent("user-a", message)
    assert "name section" in result["reply"]
    assert "doesn't determine which jobs" in result["reply"]
    assert "legal name" in result["reply"]
    assert "isn't fully complete" in result["reply"]
    assert not result["reply"].startswith("Yes")
    assert result["profile_status"]["completed"] is False
    assert result["updated_profile"]["changed_fields"] == []
    assert saved == before
    cursor.execute.assert_not_called()
    db.commit.assert_not_called()
    update.assert_not_called()
    llm.assert_not_called()


def test_exact_reported_conversation_answers_each_intent_then_accepts_nickname():
    saved = profile()
    db, cursor = MagicMock(), MagicMock()
    first = _handle_onboarding_step(db, cursor, "user-a", saved, "I'm I give my name?")
    why = _handle_onboarding_step(db, cursor, "user-a", saved, "why you ask my name?")
    reason = _handle_onboarding_step(db, cursor, "user-a", saved, "what is the reason you need my name?")
    assert first["reply"].startswith("Yes")
    assert "name section" in why["reply"] and "name section" in reason["reply"]
    cursor.execute.assert_not_called()
    assert saved["full_name"] == "" and saved["onboarding_step"] == "full_name"
    next_turn = _handle_onboarding_step(db, cursor, "user-a", saved, "Dhanu")
    assert saved["full_name"] == "Dhanu"
    assert "skills" in next_turn["reply"].lower()


@pytest.mark.parametrize("message", ["Is my profile complete?", "what details are missing?",
                                     "is my profile not fully complete?", "what is remaining in my profile?"])
def test_status_uses_actual_missing_facts_not_default_fresher_or_blank_fields(message):
    saved = profile(full_name="Dhanush", skills=["Python"])
    result = _profile_clarification(saved, message)
    assert result["profile_status"]["missing_fields"] == [
        "experience (fresher or years/months)", "target roles", "preferred city (or Remote/Any)"]
    assert "isn't fully complete" in result["reply"]
    assert "start again" in result["reply"]
    assert saved["experience_provided"] is False


@pytest.mark.parametrize("message", ["I don't want to share my name", "skip my name",
                                     "I prefer not to give my name", "I don't want to provide my details"])
def test_refusal_does_not_fake_completion_or_force_legal_name(message):
    saved = profile()
    result = _profile_clarification(saved, message)
    assert "you decide what to share" in result["reply"]
    assert "isn't fully complete" in result["reply"]
    assert "without finishing your profile" in result["reply"]
    assert result["profile_status"]["completed"] is False
    assert saved["full_name"] == "" and not saved["profile_completed"]


@pytest.mark.parametrize("message,expected", [
    ("why do you ask for my skills?", "compare what you know"),
    ("what is the reason you need my experience?", "experience section"),
    ("why do you need my target role?", "jobs you want"),
    ("why do you ask for my location?", "home address"),
    ("why do you need my resume?", "optional"),
    ("why are you asking this?", "name section"),
])
def test_other_field_purposes_and_implicit_current_field(message, expected):
    assert expected in _profile_clarification(profile(), message)["reply"]


def test_complete_profile_status_does_not_ask_for_already_saved_fields():
    saved = profile(full_name="Dhanush", skills=["Python"], preferred_titles=["AI Engineer"],
                    preferred_locations=["Chennai"], experience_provided=True, profile_completed=1,
                    onboarding_step="completed")
    result = _profile_clarification(saved, "Is my profile complete?")
    assert result["profile_status"]["completed"] is True
    assert result["profile_status"]["missing_fields"] == []
    assert "is complete" in result["reply"]
    assert "Are you a fresher" not in result["reply"]


def test_facts_filled_but_resume_step_pending_is_distinct_from_missing_required_details():
    saved = profile(full_name="Dhanush", skills=["Python"], preferred_titles=["AI Engineer"],
                    preferred_work_mode="remote", experience_provided=True, onboarding_step="resume")
    result = _profile_clarification(saved, "Is my profile complete?")
    assert result["profile_status"] == {"completed": False, "missing_fields": [], "resume_decision_pending": True}
    assert "resume is optional" in result["reply"].lower()
    assert "skip" in result["reply"]


def test_stale_completion_flag_does_not_claim_missing_facts_are_complete():
    assert _profile_completion_status(profile(profile_completed=1))["completed"] is False


def test_general_profile_purpose_explains_all_sections_not_only_the_name():
    result = _profile_clarification(profile(), "why do you need these details?")
    assert "skills and experience" in result["reply"]
    assert "target roles and locations" in result["reply"]
    assert "resume is optional" in result["reply"]


@pytest.mark.parametrize("message", ["show machine learning jobs in Madurai", "why are no jobs available in Madurai?",
                                     "my name is Dhanush", "I am a fresher"])
def test_unrelated_searches_and_real_profile_data_keep_their_existing_routes(message):
    assert _profile_clarification(profile(), message) is None
