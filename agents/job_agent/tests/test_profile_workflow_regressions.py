from unittest.mock import MagicMock, patch
import copy
import json
import re
import pytest

from job_agent.chat_service import (
    _apply_profile_updates,
    _detect_message_profile_updates,
    _handle_onboarding_step,
    _get_top_matched_jobs,
    chat_with_job_agent,
    extract_work_mode_from_text,
)
from job_agent.skills import extract_skills_from_user_message
from job_agent.tn_location import extract_known_locations, location_matches_preferences


def _profile(step="experience"):
    return {
        "full_name": "Lakshmandhanu",
        "skills": ["Mathematics"],
        "preferred_titles": [],
        "preferred_locations": [],
        "preferred_work_mode": "",
        "experience_years": 0.0,
        "experience_provided": False,
        "resume_original_name": "",
        "profile_completed": 0,
        "onboarding_step": step,
    }


def test_cross_field_profile_extraction_preserves_every_requested_field():
    updates = _detect_message_profile_updates(
        "I have 1.6 years experience, Python and Fast API skills, AI Engineer jobs in Chennai and Bangalore, office only"
    )
    assert updates["experience_years"] == 1.6
    assert updates["skills_to_add"] == ["Python", "FastAPI"]
    assert updates["titles_to_set"] == ["AI Engineer"]
    assert updates["locations_to_set"] == ["Chennai", "Bengaluru"]
    assert updates["preferred_work_mode"] == "office"


def test_skill_aliases_and_location_typo_normalize_without_dropping_values():
    skills = extract_skills_from_user_message(
        "AI agents, Gen AI, LLM, REST API, FAST API, Flask, Machine learning, Deep Learning, CNN, Python, CI/CD, MLOPs"
    )
    assert skills == [
        "AI Agents", "Generative AI", "LLM", "REST API", "FastAPI", "Flask",
        "Machine Learning", "Deep Learning", "CNN", "Python", "CI/CD", "MLOps",
    ]
    assert extract_known_locations("Thanjavur, Trichy, Madhurai") == [
        "Thanjavur", "Tiruchirappalli", "Madurai",
    ]


def test_office_and_any_work_modes_are_normalized_and_match_legacy_job_data():
    for text in ("work from office", "work form Office only", "Work from office", "WFO"):
        assert extract_work_mode_from_text(text) == "office"
    assert extract_work_mode_from_text("no preference") == "any"
    assert extract_work_mode_from_text("any") == "any"
    assert location_matches_preferences("Chennai", "onsite", ["office"])


def test_experience_status_is_structured_and_six_months_converts_to_half_year():
    assert _detect_message_profile_updates("I am a fresher")["experience_status"] == "fresher"
    updates = _detect_message_profile_updates("6 months experience")
    assert updates["experience_years"] == 0.5
    assert updates["experience_status"] == "experienced"
    assert _detect_message_profile_updates("I have experience")["experience_status"] == "needs_years"


def test_skills_merge_and_explicit_remove_persist_through_profile_update():
    db, cursor = MagicMock(), MagicMock()
    profile = {**_profile(), "skills": ["Mathematics"]}
    profile, changed = _apply_profile_updates(db, cursor, "user-1", profile, {"skills_to_add": ["Python", "MLOps"]})
    assert profile["skills"] == ["Mathematics", "Python", "MLOps"]
    assert "skills" in changed
    profile, changed = _apply_profile_updates(db, cursor, "user-1", profile, {"skills_to_remove": ["Mathematics"]})
    assert profile["skills"] == ["Python", "MLOps"]
    assert "skills" in changed
    assert db.commit.call_count == 2


def test_off_step_skills_are_saved_and_experience_remains_the_next_missing_field():
    db, cursor = MagicMock(), MagicMock()
    profile = _profile("experience")
    result = _handle_onboarding_step(db, cursor, "user-1", profile, "Python, CI/CD, MLOPs")
    assert profile["skills"] == ["Mathematics", "Python", "CI/CD", "MLOps"]
    assert profile["experience_provided"] is False
    assert "how many years" in result["reply"].lower()
    assert result["updated_profile"]["skills"] == profile["skills"]


def test_explicit_name_corrections_during_skills_step_update_name_and_keep_skills_prompt():
    for utterance in (
        "my full name is dhanush",
        "can you update my name is Dhanush",
    ):
        db, cursor = MagicMock(), MagicMock()
        profile = {
            **_profile("skills"),
            "full_name": "Dhanu",
            "skills": [],
            "experience_provided": False,
        }

        result = _handle_onboarding_step(db, cursor, "user-1", profile, utterance)

        assert profile["full_name"] == "Dhanush"
        assert profile["onboarding_step"] == "skills"
        assert "Dhanush" in result["reply"]
        assert "technical **skills**" in result["reply"]
        assert result["updated_profile"]["full_name"] == "Dhanush"
        assert result["updated_profile"]["changed_fields"] == ["full name"]
        assert db.commit.call_count == 2  # name update, then onboarding-step persistence


def test_related_remote_and_other_location_quick_actions_use_distinct_filters():
    profile = {
        **_profile("completed"),
        "skills": ["Python", "FastAPI"],
        "preferred_titles": ["AI Engineer"],
        "preferred_locations": ["Tiruchirappalli", "Madurai"],
        "preferred_work_mode": "office",
        "experience_years": 1.6,
        "experience_provided": True,
        "profile_completed": 1,
    }
    db = MagicMock()
    db.cursor.return_value = MagicMock()
    related_job = {"id": 1, "title": "Generative AI Engineer", "company": "A", "location": "Tiruchirappalli", "work_mode": "onsite"}
    other_job = {"id": 2, "title": "AI Engineer", "company": "B", "location": "Chennai", "work_mode": "onsite"}
    remote_job = {"id": 3, "title": "AI Engineer", "company": "C", "location": "Remote", "work_mode": "remote"}

    def run(action, jobs):
        with (
            patch("job_agent.chat_service.get_db", return_value=db),
            patch("job_agent.chat_service._get_user_profile_and_missing", return_value=(profile.copy(), [])),
            patch("job_agent.chat_service._handle_onboarding_step", return_value=None),
            patch("job_agent.chat_service._get_top_matched_jobs", return_value=(jobs, False)) as search,
            patch("job_agent.chat_service.requests.post") as llm,
        ):
            response = chat_with_job_agent("user-1", action)
        llm.assert_not_called()
        return response, search

    response, related = run("SEARCH_RELATED_ROLES", [related_job])
    assert response["matched_jobs"] == [related_job]
    assert related.call_args.kwargs["strict_titles"] is True
    assert "generative ai engineer" in related.call_args.kwargs["title_filter"]

    response, other = run("SEARCH_OTHER_LOCATIONS", [other_job])
    assert response["matched_jobs"] == [other_job]
    assert other.call_args.kwargs["limit"] == 6
    assert other.call_args.kwargs["excluded_locations"] == ["Tiruchirappalli", "Madurai"]
    assert other.call_args.kwargs["strict_titles"] is True

    response, remote = run("SEARCH_REMOTE_JOBS", [remote_job])
    assert response["matched_jobs"] == [remote_job]
    assert remote.call_args.kwargs["work_mode_filter"] == "remote"
    assert remote.call_args.kwargs["location_filter"] == ["Remote"]

    related_empty, _ = run("SEARCH_RELATED_ROLES", [])
    other_empty, _ = run("SEARCH_OTHER_LOCATIONS", [])
    remote_empty, _ = run("SEARCH_REMOTE_JOBS", [])
    assert "related roles" in related_empty["reply"].lower()
    assert "other supported locations" in other_empty["reply"].lower()
    assert "remote jobs" in remote_empty["reply"].lower()


class _ProfileCursor:
    """Small SQL profile store for an in-process, multi-turn chat regression."""

    def __init__(self, store):
        self.store = store
        self.row = None

    def execute(self, query, params=()):
        normalized = " ".join(query.lower().split())
        if normalized.startswith("select") and "user_job_profiles" in normalized:
            self.row = copy.deepcopy(self.store)
        elif normalized.startswith("update user_job_profiles"):
            set_clause = query.split("WHERE", 1)[0]
            columns = re.findall(r"([a-z_]+)\s*=\s*%s", set_clause, re.IGNORECASE)
            for column, value in zip(columns, params):
                self.store[column] = copy.deepcopy(value)
            for column, value in re.findall(r"([a-z_]+)\s*=\s*'([^']*)'", set_clause, re.IGNORECASE):
                self.store[column] = value
            for column, value in re.findall(r"([a-z_]+)\s*=\s*([01])(?:[,\s]|$)", set_clause, re.IGNORECASE):
                self.store[column] = int(value)

    def fetchone(self):
        return copy.deepcopy(self.row)

    def fetchall(self):
        return []

    def close(self):
        pass


class _ProfileDatabase:
    def __init__(self):
        self.profile = {
            "user_id": "user-1", "full_name": "", "education": "", "skills": "[]",
            "preferred_titles": "[]", "preferred_locations": "[]", "preferred_work_mode": "",
            "experience_years": 0.0, "experience_provided": 0, "resume_original_name": "",
            "profile_completed": 0, "plan_tier": "free", "onboarding_step": "full_name",
        }

    def cursor(self, dictionary=True):
        return _ProfileCursor(self.profile)

    def commit(self):
        pass

    def close(self):
        pass


def test_name_correction_after_nickname_keeps_onboarding_on_skills():
    database = _ProfileDatabase()
    with patch("job_agent.chat_service.get_db", return_value=database):
        first = chat_with_job_agent("user-1", "Dhanu")
        corrected = chat_with_job_agent("user-1", "my full name is dhanush")

    assert "primary technical **skills**" in first["reply"]
    assert "I’ll use **Dhanush**" in corrected["reply"]
    assert "primary technical **skills**" in corrected["reply"]
    assert database.profile["full_name"] == "Dhanush"
    assert database.profile["onboarding_step"] == "skills"


def test_role_correction_during_skills_replaces_saved_role_without_skipping_skills():
    database = _ProfileDatabase()
    database.profile.update(full_name="Marimuthu", preferred_titles='["AI Engineer"]', onboarding_step="skills")
    with patch("job_agent.chat_service.get_db", return_value=database), patch(
        "job_agent.chat_service._get_top_matched_jobs"
    ) as search:
        request = chat_with_job_agent("user-1", "hello i want to change the role before we move to skills")
        assert "target role" in request["reply"]
        assert json.loads(database.profile["preferred_titles"]) == ["AI Engineer"]
        answer = chat_with_job_agent("user-1", "Data Analyst", history=[
            {"role": "assistant", "content": request["reply"]},
        ])
    assert json.loads(database.profile["preferred_titles"]) == ["Data Analyst"]
    assert answer["updated_profile"]["changed_fields"] == ["target job titles"]
    assert "technical **skills**" in answer["reply"]
    search.assert_not_called()


def test_location_correction_blocks_resume_skip_until_replacement_is_supplied():
    database = _ProfileDatabase()
    database.profile.update(
        full_name="Marimuthu", skills='["Python"]', experience_provided=1,
        preferred_titles='["AI Engineer"]', preferred_locations='["Tiruchirappalli"]',
        onboarding_step="resume",
    )
    with patch("job_agent.chat_service.get_db", return_value=database), patch(
        "job_agent.chat_service._get_top_matched_jobs"
    ) as search:
        request = chat_with_job_agent("user-1", "no no i want to change my preferred location")
        assert "preferred location" in request["reply"]
        assert json.loads(database.profile["preferred_locations"]) == ["Tiruchirappalli"]
        reminder = chat_with_job_agent("user-1", "skip", history=[
            {"role": "assistant", "content": request["reply"]},
        ])
        assert "preferred location" in reminder["reply"]
        assert database.profile["profile_completed"] == 0
        changed = chat_with_job_agent("user-1", "Bengaluru", history=[
            {"role": "assistant", "content": reminder["reply"]},
        ])
    assert json.loads(database.profile["preferred_locations"]) == ["Bengaluru"]
    assert changed["updated_profile"]["changed_fields"] == ["preferred locations"]
    assert "skip" in changed["reply"].lower()
    search.assert_not_called()


def test_direct_correction_replaces_location_without_adding_old_city():
    database = _ProfileDatabase()
    database.profile.update(
        full_name="Marimuthu", skills='["Python"]', experience_provided=1,
        preferred_titles='["AI Engineer"]', preferred_locations='["Tiruchirappalli"]',
        onboarding_step="resume",
    )
    with patch("job_agent.chat_service.get_db", return_value=database):
        response = chat_with_job_agent("user-1", "change my preferred location to Madurai")
    assert json.loads(database.profile["preferred_locations"]) == ["Madurai"]
    assert "Madurai" in response["reply"]


def test_corrected_location_is_used_when_resume_is_skipped():
    database = _ProfileDatabase()
    database.profile.update(
        full_name="Marimuthu", skills='["Python"]', experience_provided=1,
        preferred_titles='["AI Engineer"]', preferred_locations='["Tiruchirappalli"]',
        onboarding_step="resume",
    )
    with patch("job_agent.chat_service.get_db", return_value=database), patch(
        "job_agent.chat_service._get_top_matched_jobs", return_value=([], False)
    ) as search:
        changed = chat_with_job_agent("user-1", "change my preferred location to Bengaluru")
        result = chat_with_job_agent("user-1", "skip", history=[
            {"role": "assistant", "content": changed["reply"]},
        ])
    assert search.call_args.kwargs["location_filter"] == ["Bengaluru"]
    assert "Bengaluru" in result["reply"]
    assert "Tiruchirappalli" not in result["reply"]


def test_location_correction_clears_conflicting_old_work_mode():
    database = _ProfileDatabase()
    database.profile.update(full_name="Marimuthu", preferred_locations='["Tiruchirappalli"]',
                            preferred_work_mode="office", onboarding_step="skills")
    with patch("job_agent.chat_service.get_db", return_value=database):
        remote = chat_with_job_agent("user-1", "change my preferred location to Remote")
        assert remote["updated_profile"]["preferred_work_mode"] == "remote"
        assert json.loads(database.profile["preferred_locations"]) == ["Remote"]
        city = chat_with_job_agent("user-1", "change my preferred location to Pune")
    assert city["updated_profile"]["preferred_work_mode"] == ""
    assert json.loads(database.profile["preferred_locations"]) == ["Pune"]


def test_invalid_experience_correction_and_cancellation_keep_original_values():
    database = _ProfileDatabase()
    database.profile.update(full_name="Marimuthu", skills='["Python"]',
                            experience_provided=1, experience_years=2.0,
                            preferred_titles='["AI Engineer"]', onboarding_step="preferred_locations")
    with patch("job_agent.chat_service.get_db", return_value=database):
        request = chat_with_job_agent("user-1", "I want to change my experience")
        invalid = chat_with_job_agent("user-1", "100 years", history=[
            {"role": "assistant", "content": request["reply"]},
        ])
        cancelled = chat_with_job_agent("user-1", "cancel", history=[
            {"role": "assistant", "content": invalid["reply"]},
        ])
    assert database.profile["experience_years"] == 2.0
    assert "current value is still saved" in invalid["reply"]
    assert "unchanged" in cancelled["reply"]


def test_repeated_no_name_refusal_does_not_guess_a_name():
    database = _ProfileDatabase()
    with patch("job_agent.chat_service.get_db", return_value=database):
        response = chat_with_job_agent("user-1", "what i am saying i dont have any name")
    assert "won't invent one" in response["reply"]
    assert database.profile["full_name"] == ""


def test_reopened_onboarding_name_question_preserves_memory_then_accepts_correction():
    database = _ProfileDatabase()
    database.profile.update(full_name="Dhanu", onboarding_step="skills")
    with patch("job_agent.chat_service.get_db", return_value=database):
        question = chat_with_job_agent("user-1", "I am give to my name?")
        assert "Dhanu" in question["reply"]
        assert "don’t need to enter it again" in question["reply"]
        assert question["updated_profile"]["changed_fields"] == []
        assert database.profile["full_name"] == "Dhanu"
        assert json.loads(database.profile["skills"]) == []
        for text in ("can you update my name is Dhanush", "my full name is Dhanush"):
            corrected = chat_with_job_agent("user-1", text)
            assert "I’ll use **Dhanush**" in corrected["reply"]
            assert "technical **skills**" in corrected["reply"]
        skill = chat_with_job_agent("user-1", "Python")
        assert skill["updated_profile"]["full_name"] == "Dhanush"
        assert skill["updated_profile"]["skills"] == ["Python"]
        assert database.profile["onboarding_step"] == "experience"


def test_profile_api_returns_skills_prompt_for_persisted_missing_field():
    from job_agent.app import create_app

    db, cursor = MagicMock(), MagicMock()
    db.cursor.return_value = cursor
    cursor.fetchone.return_value = {
        "user_id": "user-1", "full_name": "Dhanu", "skills": "[]",
        "preferred_titles": "[]", "preferred_locations": "[]",
        "profile_completed": 0, "experience_provided": 0,
    }
    with patch("job_agent.routes.get_db", return_value=db):
        response = create_app(testing=True).test_client().get(
            "/api/jobs/me/profile", headers={"X-Digidara-User-Id": "user-1"}
        )
    assert response.status_code == 200
    profile = response.get_json()["profile"]
    assert profile["onboarding_step"] == "skills"
    assert "technical **skills**" in profile["onboarding_prompt"]


def test_profile_api_reopens_legacy_office_only_completion():
    from job_agent.app import create_app

    db, cursor = MagicMock(), MagicMock()
    db.cursor.return_value = cursor
    cursor.fetchone.return_value = {
        "user_id": "user-1", "full_name": "Dhanush", "skills": '["Python"]',
        "preferred_titles": '["AI Engineer"]', "preferred_locations": "[]",
        "preferred_work_mode": "office", "experience_years": 1.6,
        "profile_completed": 1, "experience_provided": 1, "onboarding_step": "completed",
    }
    with patch("job_agent.routes.get_db", return_value=db):
        response = create_app(testing=True).test_client().get(
            "/api/jobs/me/profile", headers={"X-Digidara-User-Id": "user-1"}
        )
    assert response.status_code == 200
    result = response.get_json()["profile"]
    assert result["profile_completed"] == 0
    assert result["onboarding_step"] == "preferred_locations"
    assert "Which city" in result["onboarding_prompt"]


def test_remote_only_profile_keeps_location_free_completion():
    database = _ProfileDatabase()
    database.profile.update(
        full_name="Dhanush", skills='["Python"]', preferred_titles='["AI Engineer"]',
        preferred_work_mode="remote", preferred_locations="[]", experience_provided=1,
        experience_years=1.6, profile_completed=1, onboarding_step="completed",
    )
    with patch("job_agent.chat_service.get_db", return_value=database):
        result = chat_with_job_agent("user-1", "what is my preferred location?")
    assert "**Remote**" in result["reply"]
    assert result["updated_profile"]["preferred_locations"] == []


def test_completed_profile_name_correction_is_confirmed_without_model_or_job_search():
    database = _ProfileDatabase()
    database.profile.update(
        full_name="Dhanu", skills='["Python"]', preferred_titles='["Data Analyst"]',
        preferred_locations='["Chennai"]', experience_provided=1,
        profile_completed=1, onboarding_step="completed",
    )
    with (
        patch("job_agent.chat_service.get_db", return_value=database),
        patch("job_agent.chat_service.requests.post") as model,
        patch("job_agent.chat_service._get_top_matched_jobs") as search,
    ):
        response = chat_with_job_agent("user-1", "can you update my name is Dhanush")
    assert database.profile["full_name"] == "Dhanush"
    assert response["updated_profile"]["full_name"] == "Dhanush"
    assert "I’ll use **Dhanush**" in response["reply"]
    model.assert_not_called()
    search.assert_not_called()


def test_role_in_skills_step_asks_before_persisting_then_confirms_using_conversation_history():
    for role in ("AI Engineer", "AI Developer"):
        database = _ProfileDatabase()
        database.profile.update(full_name="Dhanush", onboarding_step="skills")
        with patch("job_agent.chat_service.get_db", return_value=database):
            proposal = chat_with_job_agent("user-1", role)
            assert proposal["reply"].startswith(f"Should I save **{role}** as your target role?")
            assert proposal["updated_profile"]["changed_fields"] == []
            assert json.loads(database.profile["preferred_titles"]) == []
            assert json.loads(database.profile["skills"]) == []

            # Use another service call, with persisted conversation content,
            # rather than keeping any process-local pending state.
            history = [{"role": "user", "content": role}, {"role": "assistant", "content": proposal["reply"]}]
            confirmed = chat_with_job_agent("user-1", "yes", history=history)
            assert f"Saved your target role: **{role}**" in confirmed["reply"]
            assert confirmed["updated_profile"]["preferred_titles"] == [role]
            assert "technical **skills**" in confirmed["reply"]
            assert database.profile["onboarding_step"] == "skills"
            assert json.loads(database.profile["skills"]) == []

            continued = chat_with_job_agent("user-1", "Python, Machine Learning")
            assert continued["updated_profile"]["preferred_titles"] == [role]
            assert database.profile["onboarding_step"] == "experience"


def test_declining_role_proposal_does_not_change_profile():
    profile = {**_profile("skills"), "skills": [], "preferred_titles": ["Data Analyst"]}
    db, cursor = MagicMock(), MagicMock()
    result = _handle_onboarding_step(db, cursor, "user-1", profile, "no", history=[
        {"role": "assistant", "content": "Should I save **AI Engineer** as your target role?"},
    ])
    assert profile["preferred_titles"] == ["Data Analyst"]
    assert "haven’t changed your target roles" in result["reply"]
    assert result["updated_profile"]["changed_fields"] == []
    cursor.execute.assert_not_called()
    db.commit.assert_not_called()


def test_latest_role_proposal_replaces_old_proposal_and_stale_confirmation_is_ignored():
    database = _ProfileDatabase()
    database.profile.update(full_name="Dhanush", onboarding_step="skills")
    with patch("job_agent.chat_service.get_db", return_value=database):
        engineer = chat_with_job_agent("user-1", "AI Engineer")
        developer = chat_with_job_agent("user-1", "AI Developer", history=[
            {"role": "assistant", "content": engineer["reply"]},
        ])
        confirmed = chat_with_job_agent("user-1", "yes please", history=[
            {"role": "assistant", "content": engineer["reply"]},
            {"role": "assistant", "content": developer["reply"]},
        ])
        assert confirmed["updated_profile"]["preferred_titles"] == ["AI Developer"]
        stale = chat_with_job_agent("user-1", "yes", history=[
            {"role": "assistant", "content": engineer["reply"]},
            {"role": "assistant", "content": "What are your technical skills?"},
        ])
        assert stale["updated_profile"]["preferred_titles"] == ["AI Developer"]
        assert stale["updated_profile"]["changed_fields"] == []


@pytest.mark.parametrize("reply", [
    "yes ,you can save", "Yes, you can save it.", "sure, please save this role",
    "go ahead", "please save it in my profile", "you can add this role",
    "can you save it?", "okay update my profile", "that sounds good",
    "no problem, go ahead", "I would like you to save it", "yep, save that",
])
def test_conversational_acceptance_persists_pending_role(reply):
    database = _ProfileDatabase()
    database.profile.update(full_name="Dhanush", onboarding_step="skills")
    with patch("job_agent.chat_service.get_db", return_value=database):
        proposal = chat_with_job_agent("user-1", "AI Engineer")
        response = chat_with_job_agent("user-1", reply, history=[
            {"role": "assistant", "content": proposal["reply"]},
        ])
    assert json.loads(database.profile["preferred_titles"]) == ["AI Engineer"]
    assert json.loads(database.profile["skills"]) == []
    assert "Saved your target role: **AI Engineer**" in response["reply"]
    assert "technical **skills**" in response["reply"]


@pytest.mark.parametrize("reply", [
    "no, don't save it", "please do not update my profile", "no thanks",
    "yes, but don't save it", "don't add that role", "not now",
    "nope", "cancel", "leave it unchanged", "never mind", "do not save AI Engineer",
])
def test_conversational_refusal_preserves_profile(reply):
    database = _ProfileDatabase()
    database.profile.update(full_name="Dhanush", onboarding_step="skills")
    with patch("job_agent.chat_service.get_db", return_value=database):
        proposal = chat_with_job_agent("user-1", "AI Engineer")
        response = chat_with_job_agent("user-1", reply, history=[
            {"role": "assistant", "content": proposal["reply"]},
        ])
    assert json.loads(database.profile["preferred_titles"]) == []
    assert response["updated_profile"]["changed_fields"] == []
    assert "haven’t changed your target roles" in response["reply"]


@pytest.mark.parametrize("reply", [
    "maybe", "I'm not sure", "yes if there are jobs", "save it later",
    "I don't know", "yes, are you sure?", "yes but let me think",
])
def test_uncertain_confirmation_keeps_question_pending_without_profile_changes(reply):
    database = _ProfileDatabase()
    database.profile.update(full_name="Dhanush", onboarding_step="skills")
    with patch("job_agent.chat_service.get_db", return_value=database):
        proposal = chat_with_job_agent("user-1", "AI Engineer")
        uncertain = chat_with_job_agent("user-1", reply, history=[
            {"role": "assistant", "content": proposal["reply"]},
        ])
        assert json.loads(database.profile["preferred_titles"]) == []
        assert uncertain["updated_profile"]["changed_fields"] == []
        assert uncertain["reply"].startswith("Should I save **AI Engineer**")
        confirmed = chat_with_job_agent("user-1", "yes, you can save", history=[
            {"role": "assistant", "content": uncertain["reply"]},
        ])
    assert confirmed["updated_profile"]["preferred_titles"] == ["AI Engineer"]


def test_conversational_confirmation_with_skills_saves_both_and_advances():
    database = _ProfileDatabase()
    database.profile.update(full_name="Dhanush", onboarding_step="skills")
    with patch("job_agent.chat_service.get_db", return_value=database):
        proposal = chat_with_job_agent("user-1", "AI Engineer")
        response = chat_with_job_agent("user-1", "yes save it, I know Python and Machine Learning", history=[
            {"role": "assistant", "content": proposal["reply"]},
        ])
    assert response["updated_profile"]["preferred_titles"] == ["AI Engineer"]
    assert response["updated_profile"]["skills"] == ["Python", "Machine Learning"]
    assert database.profile["onboarding_step"] == "experience"


def test_conversational_reply_proposing_different_role_requires_new_confirmation():
    database = _ProfileDatabase()
    database.profile.update(full_name="Dhanush", onboarding_step="skills")
    with patch("job_agent.chat_service.get_db", return_value=database):
        proposal = chat_with_job_agent("user-1", "AI Engineer")
        different = chat_with_job_agent("user-1", "yes, save AI Developer instead", history=[
            {"role": "assistant", "content": proposal["reply"]},
        ])
        assert different["reply"].startswith("Should I save **AI Developer**")
        assert json.loads(database.profile["preferred_titles"]) == []
        confirmed = chat_with_job_agent("user-1", "you can save it", history=[
            {"role": "assistant", "content": different["reply"]},
        ])
    assert confirmed["updated_profile"]["preferred_titles"] == ["AI Developer"]


def test_conversational_confirmation_without_pending_question_does_not_invent_role():
    database = _ProfileDatabase()
    database.profile.update(full_name="Dhanush", onboarding_step="skills")
    with patch("job_agent.chat_service.get_db", return_value=database):
        response = chat_with_job_agent("user-1", "yes, you can save")
    assert response["updated_profile"]["preferred_titles"] == []
    assert response["updated_profile"]["changed_fields"] == []


def test_name_update_during_pending_role_question_does_not_confirm_role():
    database = _ProfileDatabase()
    database.profile.update(full_name="Dhanu", onboarding_step="skills")
    with patch("job_agent.chat_service.get_db", return_value=database):
        proposal = chat_with_job_agent("user-1", "AI Engineer")
        response = chat_with_job_agent("user-1", "please update my name to Dhanush", history=[
            {"role": "assistant", "content": proposal["reply"]},
        ])
    assert response["updated_profile"]["full_name"] == "Dhanush"
    assert response["updated_profile"]["preferred_titles"] == []


def test_reported_experience_clarification_and_location_update_are_acknowledged():
    database = _ProfileDatabase()
    database.profile.update(
        full_name="Dhanush", skills='["Python"]', preferred_titles='["AI Engineer"]',
        onboarding_step="experience",
    )
    with patch("job_agent.chat_service.get_db", return_value=database):
        question = chat_with_job_agent("user-1", "I give my experince year details in this place?")
        assert "enter your work experience here" in question["reply"]
        assert database.profile["experience_provided"] == 0
        location = chat_with_job_agent("user-1", "my prefereed location is bengaluru")
        assert "Saved your preferred location: **Bengaluru**" in location["reply"]
        assert json.loads(database.profile["preferred_locations"]) == ["Bengaluru"]
        assert "how many years" in location["reply"]
        experience = chat_with_job_agent("user-1", "1.6")
        assert "Saved your experience: **1.6 years**" in experience["reply"]
        assert database.profile["onboarding_step"] == "resume"


def test_experience_typo_and_months_are_supported_during_onboarding():
    database = _ProfileDatabase()
    database.profile.update(full_name="Dhanush", skills='["Python"]', onboarding_step="experience")
    with patch("job_agent.chat_service.get_db", return_value=database):
        question = chat_with_job_agent("user-1", "experince")
        assert "How many years" in question["reply"]
        response = chat_with_job_agent("user-1", "6 months experince")
    assert response["updated_profile"]["experience_years"] == 0.5
    assert database.profile["experience_provided"] == 1


def test_reported_spoken_skills_are_saved_and_acknowledged():
    database = _ProfileDatabase()
    database.profile.update(full_name="Dhanush", onboarding_step="skills")
    with patch("job_agent.chat_service.get_db", return_value=database):
        response = chat_with_job_agent(
            "user-1", "Uh, my primary technical skills is Python. Machine Learning. Deep learning. A Agents NLP. Generative AI."
        )
    assert response["updated_profile"]["skills"] == [
        "Python", "Machine Learning", "Deep Learning", "AI Agents", "NLP", "Generative AI",
    ]
    assert "Saved your skills:" in response["reply"]
    assert database.profile["onboarding_step"] == "experience"


def _portal_job(job_id, title="AI Engineer", location="Kochi"):
    return {
        "id": job_id, "title": title, "location": location, "work_mode": "onsite",
        "company": "Example", "skills": '["Python", "Machine Learning"]',
        "experience_min": 1, "experience_max": 3, "salary_text": None,
        "description": "Build machine learning systems using Python.",
        "category": "Engineering", "external_id": str(job_id),
        "apply_url": "https://example.org/careers/ai", "published_at": None,
    }


def test_matching_job_after_first_150_listings_is_not_lost():
    cursor = MagicMock()
    cursor.fetchall.side_effect = [
        [_portal_job(1000 - index, "Software Engineer", "Bengaluru") for index in range(150)],
        [_portal_job(800, location="Bengaluru")],
    ]
    profile = {**_profile("completed"), "skills": ["Python", "Machine Learning"], "experience_years": 1.6}
    jobs, _ = _get_top_matched_jobs(
        cursor, profile, title_filter=["AI Engineer"], strict_titles=True,
        location_filter=["Bengaluru"], strict_location=True,
    )
    assert [job["id"] for job in jobs] == [800]
    assert cursor.execute.call_count == 2
    assert "j.id < %s" in cursor.execute.call_args.args[0]
    assert cursor.execute.call_args.args[1][-1] == 851


def test_other_locations_excludes_saved_city_and_includes_portal_city_outside_old_list():
    cursor = MagicMock()
    cursor.fetchall.return_value = [_portal_job(100, location="Bengaluru"), _portal_job(99, location="Kochi")]
    profile = {
        **_profile("completed"), "skills": ["Python", "Machine Learning"],
        "preferred_titles": ["AI Engineer"], "preferred_locations": ["Bengaluru"], "experience_years": 1.6,
    }
    jobs, _ = _get_top_matched_jobs(cursor, profile, strict_titles=True, excluded_locations=["Bengaluru"])
    assert [job["location"] for job in jobs] == ["Kochi"]


def test_related_roles_are_broader_than_default_matching_and_do_not_change_preferences():
    database = _ProfileDatabase()
    database.profile.update(
        full_name="Dhanush", skills='["Python", "Machine Learning"]',
        preferred_titles='["AI Engineer"]', preferred_locations='["Bengaluru"]',
        profile_completed=1, experience_provided=1, experience_years=1.6, onboarding_step="completed",
    )
    related_job = _portal_job(1, "Data Scientist", "Bengaluru")
    def search(cursor, profile, **kwargs):
        return ([related_job] if "data scientist" in kwargs.get("title_filter", []) else []), False
    with (
        patch("job_agent.chat_service.get_db", return_value=database),
        patch("job_agent.chat_service._get_top_matched_jobs", side_effect=search),
    ):
        exact = chat_with_job_agent("user-1", "show my matching jobs")
        related = chat_with_job_agent("user-1", "SEARCH_RELATED_ROLES")
    assert exact["matched_jobs"] == []
    assert related["matched_jobs"] == [related_job]
    assert json.loads(database.profile["preferred_titles"]) == ["AI Engineer"]
    assert json.loads(database.profile["preferred_locations"]) == ["Bengaluru"]


def test_resume_skip_automatically_displays_available_matching_jobs():
    database = _ProfileDatabase()
    database.profile.update(
        full_name="Dhanush", skills='["Python", "Machine Learning"]',
        preferred_titles='["AI Engineer"]', preferred_locations='["Bengaluru"]',
        experience_provided=1, experience_years=1.6, onboarding_step="resume",
    )
    job = {**_portal_job(1, location="Bengaluru"), "skills": ["Python", "Machine Learning"]}
    with (
        patch("job_agent.chat_service.get_db", return_value=database),
        patch("job_agent.chat_service._get_top_matched_jobs", return_value=([job], False)) as search,
    ):
        response = chat_with_job_agent("user-1", "skip")
    assert database.profile["profile_completed"] == 1
    assert response["show_jobs"] is True
    assert response["matched_jobs"] == [job]
    assert "AI Engineer" in response["reply"]
    assert search.call_args.kwargs["strict_titles"] is True
    assert search.call_args.kwargs["strict_location"] is True


def test_office_mode_alone_does_not_complete_profile_or_invent_a_city():
    database = _ProfileDatabase()
    database.profile.update(
        full_name="Dhanush", skills='["Python"]', preferred_titles='["AI Engineer"]',
        experience_provided=1, experience_years=1.6, onboarding_step="preferred_locations",
    )
    with patch("job_agent.chat_service.get_db", return_value=database):
        mode = chat_with_job_agent("user-1", "work from office")
        location_query = chat_with_job_agent("user-1", "send jobs in my preferred location")
        city = chat_with_job_agent("user-1", "Bengaluru")

    assert mode["updated_profile"]["preferred_work_mode"] == "office"
    assert mode["updated_profile"]["preferred_locations"] == []
    assert "Which city" in mode["reply"]
    assert database.profile["profile_completed"] == 0
    assert "haven't saved a preferred city" in location_query["reply"]
    assert location_query["matched_jobs"] == []
    assert city["updated_profile"]["preferred_locations"] == ["Bengaluru"]
    assert city["updated_profile"]["preferred_work_mode"] == "office"
    assert "resume" in city["reply"].lower()


def test_legacy_complete_office_only_profile_reopens_city_question():
    database = _ProfileDatabase()
    database.profile.update(
        full_name="Dhanush", skills='["Python"]', preferred_titles='["AI Engineer"]',
        preferred_work_mode="office", preferred_locations="[]", experience_provided=1,
        experience_years=1.6, profile_completed=1, onboarding_step="completed",
    )
    with patch("job_agent.chat_service.get_db", return_value=database):
        result = chat_with_job_agent("user-1", "what is my preferred location?")
        city = chat_with_job_agent("user-1", "Chennai")
    assert "haven't saved a preferred city" in result["reply"]
    assert result["profile_status"]["completed"] is False
    assert "resume" in city["reply"].lower()
    assert database.profile["profile_completed"] == 0


def test_experience_purpose_question_explains_profile_not_search():
    database = _ProfileDatabase()
    database.profile.update(full_name="Dhanush", skills='["Python"]', onboarding_step="experience")
    with patch("job_agent.chat_service.get_db", return_value=database):
        result = chat_with_job_agent("user-1", "why I am send this information")
    assert "experience section of your job-search profile" in result["reply"]
    assert "recommendations" not in result["reply"]
    assert result["updated_profile"]["changed_fields"] == []
    assert not database.profile["experience_provided"]


def test_search_pagination_failure_does_not_silently_return_no_matches():
    cursor = MagicMock()
    cursor.fetchall.return_value = [_portal_job(1000 - index) for index in range(150)]
    with pytest.raises(RuntimeError, match="pagination did not advance"):
        _get_top_matched_jobs(cursor, _profile(), strict_titles=True, title_filter=["AI Engineer"])


def test_exact_multiturn_conversation_persists_profile_then_executes_three_search_modes():
    database = _ProfileDatabase()
    db_context = patch("job_agent.chat_service.get_db", return_value=database)
    with db_context:
        for utterance in (
            "This is my skill, math",
            "Lakshmandhanu",
            "AI agents, Gen AI, LLM, REST API, FAST API, Flask, Machine learning, Deep Learning, CNN",
            "Python, CI/CD, MLOPs",
            "1.6",
            "AI Engineer, AI Developer",
            "work form Office only",
            "Thanjavur, Trichy, Madhurai",
            "skip",
        ):
            response = chat_with_job_agent("user-1", utterance)

    persisted = database.profile
    assert persisted["full_name"] == "Lakshmandhanu"
    assert json.loads(persisted["skills"]) == [
        "Mathematics", "AI Agents", "Generative AI", "LLM", "REST API", "FastAPI",
        "Flask", "Machine Learning", "Deep Learning", "CNN", "Python", "CI/CD", "MLOps",
    ]
    assert persisted["experience_years"] == 1.6
    assert persisted["experience_provided"] == 1
    assert json.loads(persisted["preferred_titles"]) == ["AI Engineer", "AI Developer"]
    assert json.loads(persisted["preferred_locations"]) == ["Thanjavur", "Tiruchirappalli", "Madurai"]
    assert persisted["preferred_work_mode"] == "office"
    assert persisted["profile_completed"] == 1
    assert "exact-role jobs" in response["reply"].lower()
    assert response["updated_profile"]["experience_status"] == "experienced"

    jobs = {
        "related": {"id": 1, "title": "Generative AI Engineer", "company": "A", "location": "Thanjavur", "work_mode": "onsite"},
        "other": {"id": 2, "title": "AI Engineer", "company": "B", "location": "Chennai", "work_mode": "onsite"},
        "remote": {"id": 3, "title": "AI Engineer", "company": "C", "location": "Remote", "work_mode": "remote"},
    }

    def search_stub(cursor, profile, **kwargs):
        if kwargs.get("excluded_locations"):
            return [jobs["other"]], False
        if kwargs.get("work_mode_filter") == "remote":
            return [jobs["remote"]], False
        if kwargs.get("strict_titles") and "generative ai engineer" in kwargs.get("title_filter", []):
            return [jobs["related"]], False
        return [], False

    with (
        patch("job_agent.chat_service.get_db", return_value=database),
        patch("job_agent.chat_service._get_top_matched_jobs", side_effect=search_stub) as search,
        patch("job_agent.chat_service.requests.post") as llm,
    ):
        related = chat_with_job_agent("user-1", "SEARCH_RELATED_ROLES")
        other = chat_with_job_agent("user-1", "SEARCH_OTHER_LOCATIONS")
        remote = chat_with_job_agent("user-1", "SEARCH_REMOTE_JOBS")

    assert related["matched_jobs"] == [jobs["related"]]
    assert other["matched_jobs"] == [jobs["other"]]
    assert remote["matched_jobs"] == [jobs["remote"]]
    assert search.call_count == 3  # one query per explicitly requested search mode
    llm.assert_not_called()
