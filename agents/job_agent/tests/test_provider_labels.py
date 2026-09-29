from unittest.mock import MagicMock, patch

import pytest

from job_agent.app import create_app
from job_agent.chat_service import _get_top_matched_jobs, format_job_listings_markdown
from job_agent.trust import evaluate_job_trust


@pytest.mark.parametrize("provider,label", [("adzuna", "Adzuna Job API"), ("jsearch", "RapidAPI JSearch")])
def test_provider_metadata_retained_but_hidden_from_candidate_cards(provider, label):
    job = {
        "id": 1, "title": "Software Engineer", "company": "Example",
        "location": "Bengaluru", "work_mode": "onsite", "source_type": provider,
        "external_id": "legacy-provider-id", "apply_url": "https://careers.example.org/jobs/1",
        "skills": '["Python"]', "description": "Pay a registration fee to apply for this role.",
        "experience_min": 0, "experience_max": 1, "published_at": None,
    }
    cursor = MagicMock()
    cursor.fetchall.return_value = [job]
    jobs, _ = _get_top_matched_jobs(cursor, {"skills": ["Python"], "experience_years": 0})
    assert jobs[0]["source_label"] == label
    assert jobs[0]["trust_level"] == "caution"
    rendered = format_job_listings_markdown(jobs)
    assert label not in rendered
    assert "**Source:**" not in rendered
    assert "Review With Caution" in rendered
    assert "LEFT JOIN job_sources" in cursor.execute.call_args.args[0]
    assert "s.source_type" in cursor.execute.call_args.args[0]


def test_authoritative_provider_wins_over_conflicting_listing_id():
    result = evaluate_job_trust({
        "source_type": "jsearch", "external_id": "adzuna:legacy-id",
        "apply_url": "https://careers.example.org/jobs/1",
    })
    assert result["source_label"] == "RapidAPI JSearch"


def test_admin_jobs_response_uses_stored_source_metadata():
    db, cursor = MagicMock(), MagicMock()
    db.cursor.return_value = cursor
    cursor.fetchone.return_value = {"n": 1}
    cursor.fetchall.return_value = [{
        "id": 1, "title": "Software Engineer", "external_id": "legacy-id",
        "source_type": "adzuna", "skills": "[]", "status": "active",
    }]
    with patch("job_agent.routes.get_db", return_value=db):
        response = create_app(testing=True).test_client().get(
            "/api/jobs/admin/jobs?status=active",
            headers={"X-Digidara-User-Id": "admin-test", "X-Digidara-Is-Admin": "true"},
        )
    assert response.status_code == 200
    job = response.get_json()["jobs"][0]
    assert job["source_type"] == "adzuna"
    assert job["source_label"] == "Adzuna Job API"
    assert "LEFT JOIN job_sources" in cursor.execute.call_args.args[0]
    assert "j.status=%s" in cursor.execute.call_args.args[0]
