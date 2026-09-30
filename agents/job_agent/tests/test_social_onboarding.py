import copy
from unittest.mock import MagicMock, patch

import pytest

from job_agent.chat_service import _handle_onboarding_step, _social_reply, chat_with_job_agent


def experience_profile():
    return {"full_name": "Dhanush", "skills": ["Python"], "preferred_titles": [],
            "preferred_locations": [], "preferred_work_mode": "", "experience_years": 0,
            "experience_provided": False, "profile_completed": 0, "onboarding_step": "experience"}


@pytest.mark.parametrize("message,acknowledgement", [
    ("how are you?", "Thanks for asking"), ("hi", "Good to hear from you"),
    ("how are you", "Thanks for asking"),
    ("Hello!", "Good to hear from you"), ("How are you doing?", "Thanks for asking"),
])
def test_social_turn_during_experience_is_friendly_and_read_only(message, acknowledgement):
    saved = experience_profile()
    original = copy.deepcopy(saved)
    db, cursor = MagicMock(), MagicMock()
    db.cursor.return_value = cursor
    with (patch("job_agent.chat_service.get_db", return_value=db),
          patch("job_agent.chat_service._get_user_profile_and_missing", return_value=(saved, [])),
          patch("job_agent.chat_service._get_top_matched_jobs") as search,
          patch("job_agent.chat_service.requests.post") as llm):
        result = chat_with_job_agent("user-a", message)
    assert acknowledgement in result["reply"]
    assert "fresher" in result["reply"]
    assert result["profile_status"]["missing_fields"][0].startswith("experience")
    assert result["updated_profile"]["changed_fields"] == []
    assert saved == original
    cursor.execute.assert_not_called()
    db.commit.assert_not_called()
    search.assert_not_called()
    llm.assert_not_called()


def test_reported_two_turn_exchange_then_real_experience_answer_advances():
    saved = experience_profile()
    db, cursor = MagicMock(), MagicMock()
    first = _handle_onboarding_step(db, cursor, "user-a", saved, "how are you?")
    second = _handle_onboarding_step(db, cursor, "user-a", saved, "hi", history=[
        {"role": "user", "content": "how are you?"}, {"role": "assistant", "content": first["reply"]},
    ])
    assert first["reply"] != second["reply"]
    assert "fresher" in first["reply"] and "fresher" in second["reply"]
    cursor.execute.assert_not_called()
    db.commit.assert_not_called()
    assert saved["experience_provided"] is False
    answered = _handle_onboarding_step(db, cursor, "user-a", saved, "1.6")
    assert saved["experience_years"] == 1.6 and saved["experience_provided"] is True
    assert "target" in answered["reply"].lower()


def test_greeting_does_not_consume_pending_role_confirmation():
    saved = {**experience_profile(), "skills": [], "onboarding_step": "skills"}
    original_question = "Should I save **AI Engineer** as your target role?"
    first = _social_reply(saved, "hi", [{"role": "assistant", "content": original_question}])
    assert original_question in first["reply"]
    db, cursor = MagicMock(), MagicMock()
    confirmed = _handle_onboarding_step(db, cursor, "user-a", saved, "yes, save it", [
        {"role": "assistant", "content": first["reply"]},
    ])
    assert saved["preferred_titles"] == ["AI Engineer"]
    assert "Saved your target role" in confirmed["reply"]


def test_mixed_greeting_and_experience_is_not_discarded():
    assert _social_reply(experience_profile(), "Hi, I have 2 years of experience") is None
    saved = experience_profile()
    result = _handle_onboarding_step(MagicMock(), MagicMock(), "user-a", saved, "Hi, I have 2 years of experience")
    assert saved["experience_years"] == 2
    assert "target" in result["reply"].lower()


def test_completed_profile_check_in_does_not_reopen_onboarding():
    saved = {**experience_profile(), "preferred_titles": ["AI Engineer"],
             "preferred_locations": ["Chennai"], "experience_provided": True,
             "profile_completed": 1, "onboarding_step": "completed"}
    result = _social_reply(saved, "how are you?")
    assert "What would you like help with" in result["reply"]
    assert result["profile_status"]["completed"] is True


@pytest.mark.parametrize("message", ["hi Python", "how are you? I am a fresher", "Hi, 2 years experience"])
def test_non_social_profile_facts_remain_eligible_for_normal_extraction(message):
    assert _social_reply(experience_profile(), message) is None
