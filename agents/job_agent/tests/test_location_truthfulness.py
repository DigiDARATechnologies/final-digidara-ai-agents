from unittest.mock import MagicMock, patch

from job_agent.chat_service import (
    _detect_message_profile_updates,
    chat_with_job_agent,
    format_job_listings_markdown,
)
from job_agent.compensation import extract_salary_text
from job_agent.skills import extract_skills_from_user_message
from job_agent.tn_location import extract_known_locations, location_matches_preferences


def test_location_aliases_and_remote_are_separate_dimensions():
    assert extract_known_locations("Find jobs in Trichy and Ladakh") == ["Tiruchirappalli", "Ladakh"]
    assert location_matches_preferences("Trichy, Tamil Nadu", "onsite", ["Tiruchirappalli"])
    assert not location_matches_preferences("All India", "remote", ["Tiruchirappalli"])
    assert location_matches_preferences("All India", "remote", ["Remote"])

    updates = _detect_message_profile_updates("Remote AI Engineer jobs in Trichy")
    assert updates["locations_to_set"] == ["Tiruchirappalli"]
    assert updates["preferred_work_mode"] == "remote"
    assert "AI Engineer" in updates["titles_to_set"]


def test_empty_strict_location_search_never_calls_llm_or_backfills():
    profile = {
        "full_name": "Sanjay",
        "skills": ["Python"],
        "preferred_titles": ["AI Engineer"],
        "preferred_locations": ["Chennai"],
        "preferred_work_mode": "",
        "experience_years": 0.0,
        "resume_original_name": "resume.pdf",
        "profile_completed": 1,
        "onboarding_step": "completed",
    }
    db = MagicMock()
    cursor = MagicMock()
    db.cursor.return_value = cursor

    with (
        patch("job_agent.chat_service.get_db", return_value=db),
        patch("job_agent.chat_service._get_user_profile_and_missing", return_value=(profile, [])),
        patch("job_agent.chat_service._handle_onboarding_step", return_value=None),
        patch("job_agent.chat_service._apply_profile_updates", return_value=(profile, ["preferred locations"])),
        patch("job_agent.chat_service._get_top_matched_jobs", return_value=([], False)),
        patch("job_agent.chat_service.requests.post") as post,
    ):
        result = chat_with_job_agent("user-1", "Show me jobs in Ladakh")

    assert result["show_jobs"] is True
    assert result["matched_jobs"] == []
    assert "**Ladakh**" in result["reply"]
    assert "DigiDARA portal" in result["reply"]
    assert "substitute jobs from other locations or unrelated roles" in result["reply"]
    post.assert_not_called()


def test_salary_is_recovered_only_when_explicitly_present():
    assert extract_salary_text("Python Developer - 3 LPA to 5 LPA") == "3 LPA to 5 LPA"
    assert extract_salary_text("Developer", "Compensation: ₹40,000 per month") == "₹40,000 per month"
    assert extract_salary_text("Developer", "Competitive compensation") is None


def test_marketing_skills_and_skill_labels_are_evidence_based():
    skills = extract_skills_from_user_message("I know Digital Marketing, SEO and Google Ads")
    assert {"Digital Marketing", "SEO", "Google Ads"}.issubset(set(skills))

    rendered = format_job_listings_markdown([{
        "title": "Marketing Associate",
        "company": "Example",
        "location": "Chennai",
        "skills": ["SEO", "Google Ads"],
        "matching_skills": ["SEO"],
        "missing_skills": ["SEO", "Google Ads"],
        "match_score": 70,
        "trust_score": 0,
    }])
    assert "Matched Skills:** SEO" in rendered
    assert "Missing Skills:** Google Ads" in rendered
    assert "Missing Skills:** SEO" not in rendered
    assert "General Tech Stack" not in rendered
