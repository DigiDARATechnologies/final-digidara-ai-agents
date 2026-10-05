"""Every IT role in every city each week, fresh postings only, 7-day retention."""
import json
import math
from datetime import date, datetime
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

from job_agent import automation
from job_agent.config import JOBS_RETENTION_DAYS
from job_agent.providers import adzuna
from job_agent.providers.config_loader import get_adzuna_config, get_jsearch_config, load_providers_config
from job_agent.providers.sync import sync_adzuna_sources, sync_jsearch_sources, todays_slice
from job_agent.scraper import scrape_source
from job_agent.service import prune_expired_jobs_in_session

COVERAGE = {"it_coverage": {"roles": ["Java Developer", "DevOps Engineer", "java developer", ""],
                            "cities": ["Chennai", "Madurai"], "jsearch_region": "Tamil Nadu"},
            "adzuna": {"enabled": True}, "jsearch": {"enabled": True}}


def test_searches_are_every_role_in_every_city_without_duplicates():
    queries = get_adzuna_config(COVERAGE)["queries"]
    assert queries == [{"what": "Java Developer", "where": "Chennai"}, {"what": "Java Developer", "where": "Madurai"},
                       {"what": "DevOps Engineer", "where": "Chennai"}, {"what": "DevOps Engineer", "where": "Madurai"}]
    assert get_jsearch_config(COVERAGE)["queries"] == [
        {"query": "Java Developer fresher in Tamil Nadu"}, {"query": "DevOps Engineer fresher in Tamil Nadu"}]


def test_an_explicit_query_list_still_wins_over_the_catalogue():
    config = {**COVERAGE, "adzuna": {"enabled": True, "queries": [{"what": "Tester", "where": "Salem"}]}}
    assert get_adzuna_config(config)["queries"] == [{"what": "Tester", "where": "Salem"}]


def test_the_shipped_catalogue_covers_the_missing_it_roles():
    roles = {q["what"] for q in get_adzuna_config(load_providers_config())["queries"]}
    for role in ("Java Developer", "React Developer", "Full Stack Developer", "DevOps Engineer", "Cloud Engineer",
                 "QA Engineer", "Machine Learning Engineer", "AI Engineer", "Data Engineer", "UI UX Designer"):
        assert role in roles


def test_the_daily_slice_rotates_through_every_search_within_a_week():
    searches = list(range(224))
    seen = set()
    for day in range(math.ceil(224 / 40)):
        today = todays_slice(searches, 40, date(2026, 10, 1 + day))
        assert len(today) == 40
        seen.update(today)
    assert seen == set(searches)


def test_the_daily_slice_respects_its_budget():
    assert todays_slice([1, 2, 3], 0, date(2026, 10, 1)) == []
    assert todays_slice([1, 2, 3], 10, date(2026, 10, 1)) == [1, 2, 3]
    assert todays_slice([], 5, date(2026, 10, 1)) == []


def _synced_parser_configs(sync, config):
    cursor = MagicMock()
    db = MagicMock()
    db.cursor.return_value = cursor
    with patch("job_agent.providers.sync.get_db", return_value=db):
        sync(config)
    return [json.loads(call.args[1][2]) for call in cursor.execute.call_args_list if "INSERT INTO job_sources" in call.args[0]]


def test_sources_fetch_only_postings_from_the_last_week():
    for parser in _synced_parser_configs(sync_adzuna_sources, COVERAGE):
        assert parser["max_days_old"] == JOBS_RETENTION_DAYS == 7
        assert parser["results_per_page"] == 50
    for parser in _synced_parser_configs(sync_jsearch_sources, COVERAGE):
        assert parser["date_posted"] == "week"


def test_the_worker_passes_the_freshness_filters_to_each_api():
    with patch("job_agent.providers.adzuna.fetch_and_normalize", return_value=[]) as fetch:
        scrape_source({"scraping_authorized": 1, "is_active": 1, "source_type": "adzuna", "source_url": "https://api.adzuna.com",
                       "parser_config": json.dumps({"what": "Java Developer", "where": "Chennai", "max_days_old": 7})})
    assert fetch.call_args.kwargs["max_days_old"] == 7
    with patch("job_agent.providers.jsearch.fetch_and_normalize", return_value=[]) as fetch:
        scrape_source({"scraping_authorized": 1, "is_active": 1, "source_type": "jsearch", "source_url": "https://jsearch.p.rapidapi.com",
                       "parser_config": json.dumps({"query": "Java Developer fresher in Tamil Nadu", "date_posted": "week"})})
    assert fetch.call_args.kwargs["date_posted"] == "week"


@patch("job_agent.providers.adzuna._credentials", return_value=("id", "key"))
def test_adzuna_asks_only_for_recent_postings(_credentials):
    session = MagicMock()
    session.get.return_value = MagicMock(status_code=200, json=MagicMock(return_value={"results": []}))
    adzuna.fetch_and_normalize("Java Developer", "Chennai", session=session, max_days_old=7)
    assert session.get.call_args.kwargs["params"]["max_days_old"] == 7


def test_retention_is_a_week_and_never_deletes_a_saved_or_applied_job():
    cursor = MagicMock()
    cursor.rowcount = 0
    prune_expired_jobs_in_session(cursor)
    expire, delete = (call.args for call in cursor.execute.call_args_list)
    assert expire[1] == (7, 7) and delete[1] == (7, 7)
    assert "NOT EXISTS" in delete[0] and "a.is_saved = 1" in delete[0] and "application_status IS NOT NULL" in delete[0]


@patch("job_agent.automation._record_outcome")
@patch("job_agent.automation.queue_jsearch_collection", return_value={"ready": True, "queued_count": 6})
@patch("job_agent.automation.queue_adzuna_collection", return_value={"ready": True, "queued_count": 40})
@patch("job_agent.automation.prune_expired_jobs", return_value={"success": True})
@patch("job_agent.automation._claim_today", return_value=True)
def test_the_daily_automation_prunes_after_a_week(_claim, prune, _adzuna, _jsearch, _record):
    automation.queue_due_automation(datetime(2026, 10, 1, 9, 0, tzinfo=ZoneInfo("Asia/Kolkata")))
    prune.assert_called_once_with(max_age_days=7)
