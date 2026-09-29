from unittest.mock import MagicMock, patch

from job_agent.chat_service import (
    _handle_onboarding_step,
    _matches_target_role,
    chat_with_job_agent,
)
from job_agent.skills import extract_skills_from_user_message


def _profile(step):
    return {
        "full_name": "Sanjay" if step != "full_name" else "",
        "skills": ["React"] if step not in {"full_name", "skills"} else [],
        "preferred_titles": [],
        "preferred_locations": [],
        "preferred_work_mode": "",
        "experience_years": 0.0,
        "experience_provided": False,
        "resume_original_name": "",
        "profile_completed": 0,
        "onboarding_step": step,
    }


def test_name_refusal_gets_a_helpful_answer_instead_of_repeating_prompt():
    result = _handle_onboarding_step(MagicMock(), MagicMock(), "user-1", _profile("full_name"), "I dont have name what can I do?")
    assert "No problem" in result["reply"]
    assert "nickname" in result["reply"]


def test_skill_clarification_answers_the_question_without_advancing():
    cursor = MagicMock()
    result = _handle_onboarding_step(
        MagicMock(), cursor, "user-1", _profile("skills"), "Are you asking role or my skills?"
    )
    assert "asking for your **skills**" in result["reply"]
    assert "preferred job role is a separate detail" in result["reply"]
    cursor.execute.assert_not_called()


def test_mathematics_is_a_supported_profile_skill():
    assert extract_skills_from_user_message("skills, math") == ["Mathematics"]


def test_experience_word_alone_requests_years_and_does_not_advance():
    cursor = MagicMock()
    result = _handle_onboarding_step(MagicMock(), cursor, "user-1", _profile("experience"), "experience")
    assert "How many years" in result["reply"]
    assert not any("onboarding_step=%s" in call.args[0] for call in cursor.execute.call_args_list)


def test_impossible_experience_is_rejected_without_persistence():
    cursor = MagicMock()
    result = _handle_onboarding_step(MagicMock(), cursor, "user-1", _profile("experience"), "100 years")
    assert "looks invalid" in result["reply"]
    assert "0 to 50 years" in result["reply"]
    cursor.execute.assert_not_called()


def test_valid_experience_is_explicitly_marked_as_provided():
    db = MagicMock()
    cursor = MagicMock()
    profile = _profile("experience")
    result = _handle_onboarding_step(db, cursor, "user-1", profile, "2.5 years experience")
    assert profile["experience_years"] == 2.5
    assert profile["experience_provided"] is True
    assert "target" in result["reply"].lower()
    assert any("experience_provided=1" in call.args[0] for call in cursor.execute.call_args_list)


def test_exact_role_guard_does_not_treat_python_developer_as_data_analyst():
    assert _matches_target_role("Senior Data Analyst", ["Data Analyst"])
    assert _matches_target_role("Business Intelligence Analyst", ["Data Analyst"])
    assert not _matches_target_role("Python Developer", ["Data Analyst"])
    assert not _matches_target_role("Software Engineer", ["AI Engineer"])


def test_preferred_location_reference_uses_saved_location_and_never_calls_llm_on_empty_result():
    profile = {
        **_profile("completed"),
        "full_name": "Sanjay",
        "skills": ["React", "Express.js"],
        "preferred_titles": ["AI Engineer"],
        "preferred_locations": ["Tiruchirappalli"],
        "experience_provided": True,
        "profile_completed": 1,
        "resume_original_name": "resume.pdf",
    }
    db = MagicMock()
    db.cursor.return_value = MagicMock()
    with (
        patch("job_agent.chat_service.get_db", return_value=db),
        patch("job_agent.chat_service._get_user_profile_and_missing", return_value=(profile, [])),
        patch("job_agent.chat_service._handle_onboarding_step", return_value=None),
        patch("job_agent.chat_service._get_top_matched_jobs", return_value=([], False)) as retrieve,
        patch("job_agent.chat_service.requests.post") as post,
    ):
        result = chat_with_job_agent("user-1", "It is okay, share me a job in my preferred location")

    assert result["matched_jobs"] == []
    assert "Tiruchirappalli" in result["reply"]
    assert "won’t substitute" in result["reply"]
    assert retrieve.call_args.kwargs["location_filter"] == ["Tiruchirappalli"]
    assert retrieve.call_args.kwargs["strict_location"] is True
    assert retrieve.call_args.kwargs["title_filter"] == ["AI Engineer"]
    assert retrieve.call_args.kwargs["strict_titles"] is True
    post.assert_not_called()


def test_preferred_location_question_is_answered_without_provider_dependency():
    profile = {
        **_profile("completed"),
        "full_name": "Sanjay",
        "skills": ["React"],
        "preferred_titles": ["AI Engineer"],
        "preferred_locations": ["Tiruchirappalli"],
        "experience_provided": True,
        "profile_completed": 1,
    }
    db = MagicMock()
    db.cursor.return_value = MagicMock()
    with (
        patch("job_agent.chat_service.get_db", return_value=db),
        patch("job_agent.chat_service._get_user_profile_and_missing", return_value=(profile, [])),
        patch("job_agent.chat_service._handle_onboarding_step", return_value=None),
        patch("job_agent.chat_service.requests.post") as post,
    ):
        result = chat_with_job_agent("user-1", "Share me my preferred location")

    assert result["reply"] == "Your preferred location is **Tiruchirappalli**."
    assert result["show_jobs"] is False
    post.assert_not_called()
