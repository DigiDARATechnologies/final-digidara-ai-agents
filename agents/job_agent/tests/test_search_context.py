import copy
import json
from unittest.mock import MagicMock, patch

import pytest

from job_agent.chat_service import chat_with_job_agent, _resolve_search_context, format_job_listings_markdown
from job_agent.memory import load_recent_history, sanitize_client_history


def profile(completed=True):
    return {"full_name": "Dhanush", "skills": ["SQL"], "preferred_titles": ["Data Analyst"],
            "preferred_locations": ["Bengaluru"], "preferred_work_mode": "office",
            "experience_years": 0, "experience_provided": completed,
            "profile_completed": int(completed), "onboarding_step": "completed" if completed else "skills"}


def job(job_id, title="Machine Learning Engineer", city="Madurai"):
    return {"id": job_id, "title": title, "company": "Example", "location": city,
            "work_mode": "onsite", "skills": '["Python", "Machine Learning"]',
            "description": "Develop machine learning systems.", "experience_min": 4, "experience_max": 8,
            "external_id": "adzuna:1", "source_type": "adzuna", "apply_url": "https://example.org/jobs/1"}


def chat(message, saved, rows=None, history=None):
    db, cursor = MagicMock(), MagicMock()
    db.cursor.return_value = cursor
    cursor.fetchall.return_value = rows or []
    with (patch("job_agent.chat_service.get_db", return_value=db),
          patch("job_agent.chat_service._get_user_profile_and_missing", return_value=(saved, [])),
          patch("job_agent.chat_service._apply_profile_updates") as update,
          patch("job_agent.chat_service.requests.post") as llm):
        result = chat_with_job_agent("user-a", message, history)
    update.assert_not_called()
    llm.assert_not_called()
    db.commit.assert_not_called()
    return result


@pytest.mark.parametrize("completed", [True, False])
def test_explicit_ml_city_search_overrides_preferences_without_saving_or_blending_away_jobs(completed):
    saved = profile(completed)
    before = copy.deepcopy(saved)
    result = chat("send the machine learning jobs in madurai", saved,
                  [job(3), job(2, city="Chennai"), job(1, title="Python Developer")])
    assert [item["id"] for item in result["matched_jobs"]] == [3]
    assert result["search_context"]["locations"] == ["Madurai"]
    assert "Machine Learning Engineer" in result["search_context"]["titles"]
    assert saved == before
    assert result["updated_profile"]["preferred_locations"] == ["Bengaluru"]
    assert "Adzuna" not in result["reply"]
    assert "4-8 yrs" in result["reply"]


def test_no_results_means_no_portal_match_not_invented_or_substituted_jobs():
    result = chat("send machine learning jobs in Madurai", profile(), [job(1, city="Chennai")])
    assert result["matched_jobs"] == []
    assert "**Madurai**" in result["reply"]
    assert "DigiDARA portal" in result["reply"]


def test_server_saved_context_survives_restart_and_city_followup_keeps_role():
    first = chat("send machine learning jobs in Madurai", profile())
    cursor = MagicMock()
    cursor.fetchall.return_value = [{"role": "assistant", "content": first["reply"],
                                    "metadata": json.dumps({"response": first})}]
    history = load_recent_history(cursor, "user-a", "conversation-a")
    second = chat("what about Chennai?", profile(), [job(2, city="Chennai"), job(1)], history)
    assert [item["id"] for item in second["matched_jobs"]] == [2]
    assert second["search_context"]["titles"] == first["search_context"]["titles"]
    assert second["search_context"]["locations"] == ["Chennai"]


def test_explicit_new_search_replaces_previous_role_and_city():
    previous = _resolve_search_context("send machine learning jobs in Madurai", profile())
    context = _resolve_search_context("show Data Analyst jobs in Trichy", profile(),
                                      [{"role": "assistant", "search_context": previous}])
    assert context["titles"] == ["Data Analyst"]
    assert context["locations"] == ["Tiruchirappalli"]


@pytest.mark.parametrize("action", ["SEARCH_RELATED_ROLES", "SEARCH_OTHER_LOCATIONS", "SEARCH_REMOTE_JOBS"])
def test_search_buttons_use_last_search_not_saved_unrelated_role(action):
    previous = _resolve_search_context("send machine learning jobs in Madurai", profile())
    result = chat(action, profile(), history=[{"role": "assistant", "search_context": previous}])
    assert "Data Analyst" not in result["search_context"]["titles"]
    if action == "SEARCH_REMOTE_JOBS":
        assert result["search_context"]["locations"] == ["Remote"]
    elif action == "SEARCH_OTHER_LOCATIONS":
        assert result["search_context"]["excluded_locations"] == ["Madurai"]


def test_unknown_city_is_not_replaced_by_saved_bengaluru():
    context = _resolve_search_context("send machine learning jobs in Atlantis", profile())
    assert context["locations"] == ["Atlantis"]


@pytest.mark.parametrize("message,role", [("send python jobs in Madurai", "Python Developer"),
                                         ("find data science roles in Chennai", "Data Scientist"),
                                         ("show ML openings in Madurai", "ML Engineer")])
def test_shorthand_search_roles_are_not_saved_skills(message, role):
    context = _resolve_search_context(message, profile())
    assert role in context["titles"]


def test_refresh_preserves_search_scope_but_resets_seen_jobs():
    previous = _resolve_search_context("send machine learning jobs in Madurai", profile())
    previous["seen_job_ids"] = [3]
    context = _resolve_search_context("refresh", profile(), [{"role": "assistant", "search_context": previous}])
    assert context["locations"] == ["Madurai"]
    assert context["seen_job_ids"] == []
    assert context["work_mode"] is None  # Do not reintroduce the saved office filter.


def test_bare_more_is_a_contextual_followup_not_a_profile_search():
    previous = _resolve_search_context("send machine learning jobs in Madurai", profile())
    previous["seen_job_ids"] = [3]
    context = _resolve_search_context("more", profile(), [{"role": "assistant", "search_context": previous}])
    assert context["locations"] == ["Madurai"]
    assert context["seen_job_ids"] == [3]


def test_free_form_role_is_not_replaced_by_unrelated_saved_role():
    context = _resolve_search_context("show DevRel jobs in Madurai", profile())
    assert context["titles"] == ["Devrel"]
    assert context["locations"] == ["Madurai"]


def test_more_matches_retains_scope_and_excludes_previous_results_with_correct_sql_bind_order():
    first = chat("send machine learning jobs in Madurai", profile(), [job(7)])
    db, cursor = MagicMock(), MagicMock()
    db.cursor.return_value = cursor
    cursor.fetchall.return_value = []
    with (patch("job_agent.chat_service.get_db", return_value=db),
          patch("job_agent.chat_service._get_user_profile_and_missing", return_value=(profile(), []))):
        result = chat_with_job_agent("user-a", "Show me more jobs", [{"role": "assistant", "search_context": first["search_context"]}])
    sql, params = cursor.execute.call_args.args
    assert "j.id NOT IN (%s)" in sql
    assert params == ("user-a", 7)
    assert result["search_context"]["locations"] == ["Madurai"]
    assert "further active jobs" in result["reply"]


@pytest.mark.parametrize("message", ["my skills are Machine Learning", "update my target role to AI Engineer",
                                     "are you asking role or skills?", "show the job description"])
def test_profile_and_detail_messages_are_not_ad_hoc_searches(message):
    assert _resolve_search_context(message, profile()) is None


def test_untrusted_client_history_cannot_inject_structured_search_context():
    clean = sanitize_client_history([{"role": "assistant", "content": "hello",
                                     "search_context": {"titles": ["invented"]}}])
    assert all("search_context" not in turn for turn in clean)


@pytest.mark.parametrize("metadata", ['{"response": []}', '{bad json}',
                                       '{"response":{"search_context":{"titles":"bad"}}}'])
def test_malformed_optional_search_memory_fails_safely(metadata):
    cursor = MagicMock()
    cursor.fetchall.return_value = [{"role": "assistant", "content": "hello", "metadata": metadata}]
    assert load_recent_history(cursor, "u", "c") == [{"role": "assistant", "content": "hello"}]


@pytest.mark.parametrize("badge", ["Aggregator Listing (via Adzuna)", "Aggregator Listing (via RapidAPI JSearch)"])
def test_provider_badges_are_neutral_in_candidate_cards_and_zero_match_is_not_invented(badge):
    rendered = format_job_listings_markdown([{**job(1), "trust_badge": badge,
                                            "match_percentage": 0, "match_score": 0}])
    assert "Adzuna" not in rendered and "RapidAPI" not in rendered
    assert "Match 0%" in rendered


@pytest.mark.parametrize("message", ["find me jobs in chennai", "send me jobs in Chennai", "show me jobs in chennai"])
def test_me_in_a_request_is_never_a_role(message):
    # "find me jobs in Chennai" used to search for the role "Me", so every
    # follow-up (Search related roles) found nothing in a city full of jobs.
    context = _resolve_search_context(message, profile(), [])
    assert context is not None
    assert "Me" not in context["titles"] and "me" not in context["role_label"].lower().split()
    assert context["titles"] == ["Data Analyst"]  # falls back to the saved role


def test_a_bare_get_me_jobs_goes_to_the_profile_search_not_a_role_named_me():
    assert _resolve_search_context("get me jobs", profile(), []) is None


def test_me_before_a_real_role_keeps_the_role():
    context = _resolve_search_context("show me react jobs", profile(), [])
    assert context["titles"] == ["React Developer"] or context["titles"] == ["React"]
