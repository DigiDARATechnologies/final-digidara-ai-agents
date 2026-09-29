import copy
import json
from unittest.mock import MagicMock, patch

import pytest
import requests

from job_agent.chat_service import _onboarding_question_reply, chat_with_job_agent


def profile():
    return {"full_name": "Dhanush", "skills": ["Python"], "preferred_titles": [],
            "preferred_locations": [], "preferred_work_mode": "", "experience_years": 0,
            "experience_provided": False, "profile_completed": 0, "onboarding_step": "experience"}


def run(message, model_reply="You could highlight relevant projects and practice interviews.", model_error=None):
    saved = profile()
    original = copy.deepcopy(saved)
    db, cursor = MagicMock(), MagicMock()
    db.cursor.return_value = cursor
    mock_response = MagicMock()
    mock_response.ok = True
    mock_response.json.return_value = {"choices": [{"finish_reason": "stop", "message": {
        "content": json.dumps({"reply": model_reply})}}]}
    with (patch("job_agent.chat_service.get_db", return_value=db),
          patch("job_agent.chat_service._get_user_profile_and_missing", return_value=(saved, [])),
          patch("job_agent.chat_service._get_top_matched_jobs") as search,
          patch("job_agent.chat_service.OPENAI_API_KEY", "test-token"),
          patch("job_agent.chat_service.requests.post", side_effect=model_error or [mock_response]) as model):
        result = chat_with_job_agent("user-a", message)
    assert saved == original
    assert result["updated_profile"]["changed_fields"] == []
    assert result["show_jobs"] is False
    assert result["matched_jobs"] == []
    assert saved["experience_provided"] is False
    db.commit.assert_not_called()
    search.assert_not_called()
    return result, model


def test_open_career_question_is_answered_with_structured_bounded_model_context():
    result, model = run("How can I prepare for an AI Engineer interview?")
    assert "highlight relevant projects" in result["reply"]
    assert "fresher" in result["reply"]
    body = model.call_args.kwargs["json"]
    assert body["response_format"]["type"] == "json_schema"
    assert body["response_format"]["json_schema"]["strict"] is True
    assert body["messages"][0]["role"] == "system"
    assert '"experience_years": null' in body["messages"][0]["content"]
    assert "test-token" not in json.dumps(body)


def test_model_failure_gets_honest_nonempty_answer_without_advancing():
    result, _ = run("What should I learn for my career?", model_error=requests.Timeout())
    assert "can't give a reliable answer right now" in result["reply"]
    assert "fresher" in result["reply"]


@pytest.mark.parametrize("reply", ["", "I saved your profile.", "There are 10 jobs in Madurai.",
                                         "Apply here: https://example.org/jobs/1"])
def test_untrusted_or_unsafe_model_output_is_not_presented_as_evidence(reply):
    result, _ = run("What should I learn for my career?", model_reply=reply)
    assert "can't give a reliable answer right now" in result["reply"]


@pytest.mark.parametrize("message,phrase", [
    ("Who are you?", "DigiDARA Job Agent"),
    ("What does fresher mean?", "little or no full-time"),
    ("Can I skip this?", "profile will remain incomplete"),
    ("What is the capital of India?", "career help"),
])
def test_common_questions_get_safe_answers_without_external_call(message, phrase):
    result, model = run(message)
    assert phrase in result["reply"]
    model.assert_not_called()


def test_question_about_agent_name_does_not_report_candidate_name():
    result, model = run("What's your name?")
    assert "DigiDARA Job Agent" in result["reply"]
    assert "Dhanush" not in result["reply"]
    model.assert_not_called()


@pytest.mark.parametrize("message", ["Can you save AI Engineer as my role?", "Can you send jobs?",
                                     "I have 2 years of experience", "AI Engineer?"])
def test_profile_facts_and_job_requests_stay_in_existing_flows(message):
    assert _onboarding_question_reply(profile(), message) is None
